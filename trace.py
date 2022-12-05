from utils import dictget


class Trace:
    """

    """

    def __init__(self):
        self.buffer = []
        self.size = 300  # 5min

    def push(self, data):
        """
        Push dataset to buffer. Length is limited to self.size

        :param data: dictionary
        """
        self.buffer.append(data)  # append dataset
        if self.size:
            self.buffer = self.buffer[-self.size:]  # limit to max size

    def get_csv(self, key):
        """
        Get trace data as CSV

        [('value', ('device', 'val4')), ... ]

        :param key: dest, source, tuple list with keys (nested, keys allowed)
        :return:
        """
        try:
            # csv = ";".join(columns) + '\n'
            csv = ";".join([dest for dest, src in key]) + '\n'
            for d in self.buffer:
                csv += ";".join(["{}".format(dictget(d, src)) for dest, src in key]) + '\n'
        except:
            csv = ''
        return csv

    def get_chart(self, key):
        """
        Get elements from trace in single lists for charting

        [('value', ('device', 'val4')), ... ]

        :param key: dest, source, tuple list with keys (nested, keys allowed)
        :return: dictionary
        """
        chart = {dest: [] for dest, src in key}
        for d in self.buffer:
            for dest, src in key:
                chart[dest].append(dictget(d, src))
        return chart


if __name__ == "__main__":
    trace = Trace()

    trace.push({'a': 1, 'b': 10, 'c': {'q': 100}})
    trace.push({'a': 2, 'b': None, 'c': {'q': 200}})
    trace.push({'a': 3, 'b': 30})
    trace.push({'a': 4, 'b': 40, 'c': {'q': 400}})

    cfg = [('aaa', 'a'), ('bbb', 'b'), ('ccc', ('c', 'q'))]

    print(trace.buffer)

    print(trace.get_chart(cfg))

    print(trace.get_csv(cfg))
