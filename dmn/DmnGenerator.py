import uuid

from neo4j import GraphDatabase
from dkuzmin.dmn.Templates import Templates
from dkuzmin.dmn.DmnLayouter import DmnLayouter


class DmnGenerator:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.input_nodes = {}
        self.node_relations = {}
        self.dict_of_all_nodes = self.get_all_nodes()
        self.dict_of_all_nodes_pairs = self.get_all_nodes_pairs()
        self.get_future_inputs()
        self.close()

        self.semantic_shapes = []
        self.semantic_edges = {}
        self.dmndi_shapes = []
        self.dmndi_edges = []

        self.elements_children_dict = {}
        self.get_dict_id_with_children()
        self.elements_coordinates = self.layout()

        self.decision_tables = {}

        self.node_before_ks = ''

    def reduce_lists(self):
        for node in self.dict_of_all_nodes:
            print(node)

    def layout(self):
        l = DmnLayouter(self.elements_children_dict)
        return l.bfs(self.elements_children_dict, 'endevent')

    def close(self):
        self.driver.close()

    def get_all_nodes_pairs(self):
        return self.driver.session().write_transaction(self._get_all_nodes_pairs)

    def get_all_nodes(self):
        return self.driver.session().write_transaction(self._get_all_nodes)

    def if_node_is_list(self, node, node_id_list):
        if isinstance(node_id_list, list):
            node['id'] = '_'.join(node_id_list)
            node['table'] = ', '.join(node_id_list)

    def get_dict_id_with_children(self):
        for pair in self.dict_of_all_nodes_pairs:
            out_node = pair['a']
            in_node = pair['c']
            if in_node['id'] in self.elements_children_dict:
                self.elements_children_dict[in_node['id']].append(out_node['id'])
            else:
                self.elements_children_dict[in_node['id']] = [out_node['id']]
        for node in self.dict_of_all_nodes:
            if node['a']['id'] not in self.elements_children_dict:
                self.elements_children_dict[node['a']['id']] = []

    def get_future_inputs(self):
        list_of_nodes = self.driver.session().write_transaction(self._get_future_inputs)
        for node in list_of_nodes:
            if isinstance(node['n']['id'], list):
                node['n']['id'] = node['n']['id'][0]
                node['n']['name'] = '_'.join(node['n']['name'])
                node['n']['table'] = ', '.join(node['n']['name'])
            node_props = node['n']
            id_n = node_props['id']
            name = node_props['name']
            self.input_nodes[id_n] = name

    @staticmethod
    def _get_all_nodes_pairs(tx):
        result = tx.run("""MATCH (a)-[b]->(c) RETURN a, b, c""")
        records = []
        for record in result.data():
            if isinstance(record['a']['id'], list):
                record['a']['id'] = record['a']['id'][0]
                record['a']['table'] = record['a']['name']
                record['a']['name'] = '_'.join(record['a']['name'])
            if isinstance(record['c']['id'], list):
                record['c']['id'] = record['c']['id'][0]
                record['c']['table'] = record['c']['name']
                record['c']['name'] = '_'.join(record['c']['name'])
            records.append(record)
        return records

    @staticmethod
    def _get_all_nodes(tx):
        result = tx.run("""MATCH (a) RETURN a""")
        records = []
        for record in result.data():
            if isinstance(record['a']['id'], list):
                record['a']['id'] = record['a']['id'][0]
                record['a']['table'] = record['a']['name']
                record['a']['name'] = '_'.join(record['a']['name'])
            records.append(record)
        return records#[record for record in result.data()]

    @staticmethod
    def _get_future_inputs(tx):
        result = tx.run("""MATCH (n)
        WITH n, size((n)-->()) AS outR, size(()-->(n)) as inR
        WHERE inR=0
        RETURN n""")
        return [record for record in result.data()]

    def export_dmn(self, name):
        dmndi_result = Templates.dmndi.substitute(shapes='\n'.join(self.dmndi_shapes), connections='\n'.join(self.dmndi_edges))
        result = Templates.main_template.substitute(decisions='\n'.join(self.semantic_shapes), dmndi=dmndi_result)
        name = str(name).split('.')
        with open(f'../dkuzmin/solutions/{name[0]}.dmn', 'w') as file:
            file.write(result)

    def group_nodes(self):
        for pair in self.dict_of_all_nodes_pairs:
            out_node = pair['a']
            in_node = pair['c']
            x_out = self.elements_coordinates[out_node['id']][0]+180/2
            y_out = self.elements_coordinates[out_node['id']][1]
            x_in = self.elements_coordinates[in_node['id']][0]+180/2
            y_in = self.elements_coordinates[in_node['id']][1]+80
            if out_node['id'] == 'startevent':
                self.node_before_ks = in_node
                id_req = f'{out_node["id"]}'
                href = f'KnowledgeSource_{out_node["id"]}'
                requirement = Templates.semantic_authority_requirement.substitute(id_el=id_req, href_id=href)
                dmndi_edge = Templates.dmndi_dmn_connection.substitute(edge_id=out_node['id'],
                                                                       inf_req_id=f'AuthorityRequirement_{out_node["id"]}',
                                                                       x_out=x_out, y_out=y_out, x_in=x_in, y_in=y_in)
            elif out_node['id'] in self.input_nodes:
                id_req = f'{out_node["id"]}'
                href = f'InputData_{out_node["id"]}'
                requirement = Templates.semantic_requirement_input.substitute(id_el=id_req, href_id=href)
                dmndi_edge = Templates.dmndi_dmn_connection.substitute(edge_id=out_node['id'],
                                                                       inf_req_id=f'InformationRequirement_{out_node["id"]}',
                                                                       x_out=x_out, y_out=y_out, x_in=x_in, y_in=y_in)
            else:
                id_req = f'{out_node["id"]}'
                href = f'Decision_{out_node["id"]}'
                requirement = Templates.semantic_inf_requirement.substitute(id_el=id_req, href_id=href)
                dmndi_edge = Templates.dmndi_dmn_connection.substitute(edge_id=out_node['id'],
                                                                       inf_req_id=f'InformationRequirement_{out_node["id"]}',
                                                                       x_out=x_out, y_out=y_out, x_in=x_in, y_in=y_in)

            if in_node['id'] in self.semantic_edges:
                self.semantic_edges[in_node['id']].append(requirement)
            else:
                self.semantic_edges[in_node['id']] = [requirement]
            self.dmndi_edges.append(dmndi_edge)

    def build_table(self):
        for pair in self.dict_of_all_nodes_pairs:
            out_node = pair['a']
            in_node = pair['c']
            params = ['_']
            if out_node['id'] != 'startevent' and out_node['id'] != 'endevent':
                params = out_node['param']
            if ';' in params:
                params = str(params).split(';')
            elif not isinstance(params, list):
                params = [params]
            if in_node['id'] in self.decision_tables:
                self.decision_tables[in_node['id']]['in'].extend(params)
            else:
                out_par = ['_']
                if in_node['id'] != 'startevent' and in_node['id'] != 'endevent':
                    out_par = in_node['param']
                if ';' in params:
                    out_par = str(out_par).split(';')
                elif not isinstance(out_par, list):
                    out_par = [out_par]
                elif in_node['id'] == 'endevent':
                    out_par = [str(in_node['name']).capitalize()]
                self.decision_tables[in_node['id']] = {'in': params, 'out': out_par}

    def add_blocks(self):
        self.build_table()
        for node in self.dict_of_all_nodes:
            id_n = node['a']['id']
            if id_n not in self.elements_coordinates:
                self.elements_coordinates[id_n] = (150, 150)

        for node in self.dict_of_all_nodes:
            node_props = node['a']
            id_n = node_props['id']
            name = node_props['name']

            if node_props['id'] == 'startevent':
                if 'param' in self.node_before_ks:
                    nbks = self.node_before_ks['param']
                else:
                    nbks = 'solution'
                if not isinstance(nbks, list):
                    nbks = [nbks]
                self.semantic_shapes.append(Templates.semantic_knowledge_source.substitute(id=f'KnowledgeSource_{id_n}', name=';\n'.join(nbks)))
                self.dmndi_shapes.append(Templates.dmndi_dmn_shape.substitute(shape_id=id_n, element_ref=f'KnowledgeSource_{id_n}',
                                                                              x=self.elements_coordinates[id_n][0],
                                                                              y=self.elements_coordinates[id_n][1]))
            elif id_n in self.input_nodes:
                self.semantic_shapes.append(Templates.semantic_input_data.substitute(id=f'InputData_{id_n}', name=name))
                self.dmndi_shapes.append(
                    Templates.dmndi_dmn_shape.substitute(shape_id=id_n, element_ref=f'InputData_{id_n}',
                                                                              x=self.elements_coordinates[id_n][0],
                                                                              y=self.elements_coordinates[id_n][1]))
            else:
                inf_req = ['']
                if id_n in self.semantic_edges:
                    inf_req = self.semantic_edges[id_n]
                decision_table = ''
                if id_n in self.decision_tables:
                    input_entries = []
                    input_clausules = []
                    output_entries = []
                    output_clausules = []
                    table = self.decision_tables[id_n]
                    for i, text in enumerate(table['out']):
                        output_entries.append(Templates.output_enter.substitute(id=str(uuid.uuid4()), text=text))
                        output_clausules.append(Templates.output_clausule.substitute(id=str(uuid.uuid4())))
                    for i, text in enumerate(table['in']):
                        input_entries.append(Templates.input_entries.substitute(id=str(uuid.uuid4()), text=text))
                        input_clausules.append(Templates.input_clausule.substitute(clId=str(uuid.uuid4()), inpExpId=str(uuid.uuid4())))
                    decision_table = Templates.decision_table.substitute(id=id_n, inputId=str(uuid.uuid4()),
                                                                                inExprId=str(uuid.uuid4()),
                                                                                clausulesIn='\n'.join(input_clausules[:-1]), inputEntries='\n'.join(input_entries),
                                                                                outputId=str(uuid.uuid4()),
                                                                                decRuleId=str(uuid.uuid4()),
                                                                                unaryTestId=str(uuid.uuid4()),
                                                                         clausulesOut='\n'.join(output_clausules[:-1]), outputEntries='\n'.join(output_entries))
                self.semantic_shapes.append(Templates.semantic_decision.substitute(
                    id=f'Decision_{id_n}', name=name, decisionTable=decision_table, informationRequirement='\n'.join(inf_req)))
                self.dmndi_shapes.append(Templates.dmndi_dmn_shape.substitute(shape_id=id_n, element_ref=f'Decision_{id_n}',
                                                                              x=self.elements_coordinates[id_n][0],
                                                                              y=self.elements_coordinates[id_n][1]))
