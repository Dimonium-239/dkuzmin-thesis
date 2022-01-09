from os import listdir
from os.path import splitext

from dkuzmin.dmn.DmnGenerator import DmnGenerator
from dkuzmin.dmn.Bpmn2Neo4j import Bpmn2Neo4j
from pm4pybpmn.objects.bpmn.importer.bpmn20 import import_bpmn


class Main:
    def __init__(self, url, user, password):
        self.url = url
        self.user = user
        self.password = password

    @staticmethod
    def xml_to_bpmn_graph(path):
        return import_bpmn(path)

    def bpmn2dmn(self, name):
        bpmn_graph = self.xml_to_bpmn_graph(f'../tpaszun/src/solutions/{name}')
        b2n = Bpmn2Neo4j(self.url, self.user, self.password)
        b2n.add_all_nodes(bpmn_graph)
        b2n.connect_all_nodes(bpmn_graph)
        b2n.remove_parallel_gates()
        try:
            b2n.group_executive_gateways()
        except:
            b2n.delete_cycles()
            b2n.group_executive_gateways()
        b2n.find_max_spanning_tree()
        b2n.close()

        dg = DmnGenerator(self.url, self.user, self.password)

        dg.group_nodes()
        dg.add_blocks()
        dg.export_dmn(f'{name}')

    def solve_all_problem(self):
        for file in listdir(f'../tpaszun/src/solutions/'):
            if splitext(file)[1] == '.bpmn':
                self.bpmn2dmn(file)


if __name__ == '__main__':
    m = Main('bolt://localhost:7687/neo4j', 'neo4j',
                     'p34TT5NlNuThrrYQGNe-ybdPaJAs7bsMoTmEu2Lvjs4')
    m.solve_all_problem()
