from neo4j import GraphDatabase


class Bpmn2Neo4j:

    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.clear_db()

    def close(self):
        self.driver.close()

    def clear_db(self):
        with self.driver.session() as session:
            session.write_transaction(self._clear_db)
            session.write_transaction(self._reduce_lists)

    def connect_two_nodes(self, source_id, target_id, id_c, param, name):
        with self.driver.session() as session:
            connection = session.write_transaction(self._create_connection, source_id, target_id, id_c, param, name)
            session.write_transaction(self._reduce_lists)
            print(connection)

    def group_executive_gateways(self):
        with self.driver.session() as session:
            session.write_transaction(self._group_ex_gate)
            session.write_transaction(self._reduce_lists)

    def remove_oneway_gates(self):
        with self.driver.session() as session:
            session.write_transaction(self._remove_oneway_gates)
            session.write_transaction(self._reduce_lists)

    def create_node(self, type_of_node, name, id_n):
        with self.driver.session() as session:
            node = session.write_transaction(self._create_node, type_of_node, name, id_n)
            session.write_transaction(self._reduce_lists)
            print(node)

    def remove_parallel_gates(self):
        with self.driver.session() as session:
            session.write_transaction(self._remove_parallel_gates)
            session.write_transaction(self._reduce_lists)

    def delete_cycles(self):
        with self.driver.session() as session:
            session.write_transaction(self._delete_cycles)
            session.write_transaction(self._reduce_lists)

    def find_max_spanning_tree(self):
        with self.driver.session() as session:
            session.write_transaction(self._find_max_spanning_tree)
            session.write_transaction(self._reduce_lists)

    def add_all_nodes(self, bpmn_graph):
        for process_id in bpmn_graph.process_elements:
            nodes = bpmn_graph.get_nodes_list_by_process_id(process_id)
            for node in nodes:
                params = node[1]
                type_of_event = params['type']
                name = params['node_name']
                id_n = params['id']
                self.create_node(type_of_event, name, id_n)

    def get_flow_id_to_conditions(self, bpmn_graph):
        id_name_flow_dict = {}
        for process_id in bpmn_graph.process_elements:
            flows = bpmn_graph.get_flows_list_by_process_id(process_id)
            for flow in flows:
                params = flow[2]
                if params['name']:
                    id_name_flow_dict[params['id']] = params['name']
        return id_name_flow_dict

    def connect_all_nodes(self, bpmn_graph):
        id_name_dict = self.get_flow_id_to_conditions(bpmn_graph)
        for flow in bpmn_graph.get_flows():
            source_id = flow[0]
            target_id = flow[1]
            node = bpmn_graph.get_node_by_id(source_id)
            id_c = flow[2]['id']
            if id_c in node[1]['incoming']:
                source_id, target_id = target_id, source_id
            name = ['', -1]
            if id_c in id_name_dict:
                name = str(id_name_dict[id_c])[1:-1].split(',')
            self.connect_two_nodes(source_id, target_id, id_c, name[0], name[1])

    @staticmethod
    def _remove_parallel_gates(tx):
        tx.run("""MATCH (a)-[c1:FLOW]->(b:parallelGateway)-[c2:FLOW]->(c:parallelGateway)-[c3:FLOW]->(d)
            CREATE (a)-[:FLOW {name: CASE WHEN c1.name > c3.name THEN c1.name ELSE c3.name END, id:c3.id}]->(d)
            RETURN a, d""")
        tx.run(
            f"""MATCH (a)-[c1:FLOW]->(b:parallelGateway)-[c2:FLOW]->(c)
            CREATE (a)-[:FLOW {{name: CASE WHEN c1.name > c2.name THEN c1.name ELSE c2.name END, id:c2.id}}]->(c)
            RETURN a, c"""
        )
        tx.run("""MATCH m = ()-[c1:FLOW]->(b:parallelGateway)-[c2:FLOW]->()
                DELETE c1, c2, b""")

    @staticmethod
    def _create_connection(tx, sourceId, targetId, id_c, param, name):
        par = ''
        if len(param) > 0:
            par = f"SET a.param = \"{param}\""
        tx.run(
            f"""MATCH (a), (b)
                WHERE a.id = "{sourceId}" AND b.id = "{targetId}"
                {par}
                CREATE (a)-[r:FLOW {{id: "{id_c}", name: {name}}}]->(b)
                RETURN type(r), r.name"""
        )

    @staticmethod
    def _remove_oneway_gates(tx):
        tx.run("""MATCH (eg1:exclusiveGateway)
                    MATCH a = (n1)-[f1:FLOW]->(eg2:exclusiveGateway)-[f2:FLOW]->(n2)
                    WITH eg1, eg2, n1, n2, a, f1, f2, size((eg1)-->()) AS outR, size(()-->(eg1)) as inR
                    WHERE outR=1 and inR=1 and eg1=eg2
                    CREATE (n1)-[:FLOW {{name: CASE WHEN f1.name > f2.name THEN f1.name ELSE f2.name END, id:f2.id}}]->(n2)
                    DELETE f1, f2, eg2""")

    @staticmethod
    def _delete_cycles(tx):
        tx.run("""MATCH cycle= (a)-[c1:FLOW]->(eg1:exclusiveGateway)-[c2:FLOW]->(eg2:exclusiveGateway)-[c3:FLOW]->(b)
            CREATE (a)-[:FLOW {name: CASE WHEN c1.name > c2.name THEN c1.name ELSE c2.name END, id:c2.id}]->(b)
            RETURN a""")
        tx.run(
            f"""MATCH (a)-[c1:FLOW]->(b:exclusiveGateway)-[c2:FLOW]->(c)
            CREATE (a)-[:FLOW {{name: CASE WHEN c1.name > c2.name THEN c1.name ELSE c2.name END, id:c2.id}}]->(c)
            RETURN a, c"""
        )
        tx.run("""MATCH m = ()-[c1:FLOW]->(b:exclusiveGateway)-[c2:FLOW]->()
                DELETE c1, c2, b""")

    @staticmethod
    def _group_ex_gate(tx):
        tx.run("""MATCH (eg1:exclusiveGateway)
                MATCH a = (n1)-[f1:FLOW]->(eg2:exclusiveGateway)-[f2:FLOW]->(n2)
                WITH eg1, eg2, n1, n2, a, f1, f2, size((eg1)-->()) AS outR, size(()-->(eg1)) as inR
                WHERE outR=1 and inR>1 and eg1=eg2
                CREATE (n1)-[:FLOW {name: CASE WHEN f1.name > f2.name THEN f1.name ELSE f2.name END, id:f1.id}]->(n2)
                RETURN n1, n2""")
        tx.run("""MATCH (eg1:exclusiveGateway)
                MATCH a = (n1)-[f1:FLOW]->(eg2:exclusiveGateway)-[f2:FLOW]->(n2)
                WITH eg1, eg2, n1, n2, a, f1, f2, size((eg1)-->()) AS outR, size(()-->(eg1)) as inR
                WHERE outR=1 and inR>1 and eg1=eg2
                DELETE f1, f2, eg2""")
        tx.run("""MATCH (eg1:exclusiveGateway)
                MATCH a = (n1)-[f1:FLOW]->(eg2:exclusiveGateway)-[f2:FLOW]->(n2)
                WITH eg1, eg2, n1, n2, a, f1, f2, size((eg1)-->()) AS outR, size(()-->(eg1)) as inR
                WHERE outR>1 and inR>1 and eg1=eg2
                CREATE (n1)-[:FLOW {name: CASE WHEN f1.name > f2.name THEN f1.name ELSE f2.name END, id:f2.id}]->(n2)
                RETURN a""")
        tx.run("""MATCH (eg1:exclusiveGateway)
                MATCH a = (n1)-[f1:FLOW]->(eg2:exclusiveGateway)-[f2:FLOW]->(n2)
                WITH eg1, eg2, n1, n2, a, f1, f2, size((eg1)-->()) AS outR, size(()-->(eg1)) as inR
                WHERE outR>1 and inR>1 and eg1=eg2
                DELETE f1, f2, eg2""")
        tx.run("""MATCH (eg1:exclusiveGateway)
                MATCH a = (n1)-[f1:FLOW]->(eg2:exclusiveGateway)-[f2:FLOW]->(n2)
                WITH eg1, eg2, n1, n2, a, f1, f2, size((eg1)-->()) AS outR, size(()-->(eg1)) as inR, head(collect([n1, n2])) as nodes
                WHERE outR>1 and inR=1 and eg1=eg2 AND NOT n2:endEvent
                CALL apoc.refactor.mergeNodes(nodes,{properties:"combine", mergeRels:true})
                YIELD node
                RETURN a""")
        tx.run("""MATCH ()-[f1:FLOW]->(eg:exclusiveGateway)-[f2:FLOW]->()
                DELETE f1, f2, eg""")

    @staticmethod
    def _reduce_lists(tx):
        tx.run("""MATCH r = (n:task)-[a:FLOW]->()
                        WITH r, a, n, apoc.meta.typeName(n.name) AS nTypeName, apoc.meta.typeName(a.name) AS typeName
                        WHERE typeName CONTAINS '[]' and nTypeName CONTAINS '[]'
                        WITH n, a, r, apoc.text.join(n.name, '_') AS newName
                        SET n.table = apoc.text.join(n.name, ', ')
                        SET n.id = n.id[0]
                        SET n.name = newName
                        SET a.name = 1
                        RETURN r""")

    @staticmethod
    def _create_node(tx, type_of_node, name, id_n):
        result = tx.run(f"CREATE (a:{type_of_node} {{name: \"{name}\", id: \"{id_n}\"}}) "
                        "RETURN a")
        return result.single()[0]

    @staticmethod
    def _find_max_spanning_tree(tx):
        tx.run("""MATCH r = (n:task)-[a:FLOW]->()
                                WITH r, a, n, apoc.meta.typeName(n.name) AS nTypeName, apoc.meta.typeName(a.name) AS typeName
                                WHERE typeName CONTAINS '[]' and nTypeName CONTAINS '[]'
                                WITH n, a, r, apoc.text.join(n.name, '_') AS newName
                                SET n.table = apoc.text.join(n.name, ', ')
                                SET n.id = n.id[0]
                                SET n.name = newName
                                SET a.name = 1
                                RETURN r""")
        tx.run("""MATCH(n: endEvent)
        CALL gds.alpha.spanningTree.maximum.write({
            nodeProjection: '*',
            relationshipProjection: {
                FLOW: {
                    type: 'FLOW',
                    properties: 'name',
                    orientation: 'UNDIRECTED'
                }
            },
            startNodeId: id(n),
            relationshipWeightProperty: 'name',
            writeProperty: 'MAXST',
            weightWriteProperty: 'writeCost'
        })
        YIELD
        createMillis, computeMillis, writeMillis, effectiveNodeCount
        RETURN createMillis, computeMillis, writeMillis, effectiveNodeCount;""")
        tx.run("MATCH ()-[f:FLOW]->() DELETE f")
        tx.run("""MATCH ()-[f]->() 
                CALL apoc.refactor.invert(f)
                yield input, output
                RETURN input, output""")

    @staticmethod
    def _clear_db(tx):
        tx.run("match (a) -[r] -> () delete a, r")
        tx.run("match (a) delete a")



