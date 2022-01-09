import queue


class DmnLayouter:

    def __init__(self, tree):
        self.tree = tree
        self.visited = []
        self.queue = []
        self.X = 250
        self.Y = 150


    def bfs(self, graph, x):
        level = {}
        marked = []
        que = queue.Queue()
        que.put(x)
        level[x] = (0, 0)
        marked.append(x)

        while not que.empty():
            x = que.get()
            len_children = len(graph[x])
            very_left = level[x][0]
            if len_children > 1:
                very_left = level[x][0] - self.X*(len_children/2)
            if len_children % 2 == 0:
                very_left += self.X/2
            for i in range(len_children):
                b = graph[x][i]

                if b not in marked:
                    que.put(b)
                    level[b] = (very_left, level[x][1] + self.Y)
                    very_left += self.X
                    marked.append(b)
        return level
