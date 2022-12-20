import json
import logging
import os
from datetime import datetime

from utils import dictget


class Blackbox:
    """
    Dictionaries are stored in a FIFO. In the event of an error, the memory can be saved to a file.
    The number of records held can be specified by length.

    push(): Dataset/dictionary --> JSON
    dump(): Save lines of JSON to file, e.g.: blackbox-2022-11-21 144132.jsonl
    """

    def __init__(self, size, path='', csv_config=None):
        self.path = path
        self.log = logging.getLogger('blackbox')
        self.record_lines = []
        self.size = size
        os.makedirs(path, exist_ok=True)

        self.csv_config = csv_config
        self.csv_interval_time = None



    def push(self, dataset):
        """
        Convert dataset to JSON, append \n and append to FIFO list. Limit the size to maximum.
        :param dataset: dictionary
        """
        self.record_lines.append(json.dumps(dataset) + '\n')
        self.record_lines = self.record_lines[-self.size:]  # limit to latest

        if self.csv_config:
            self.csv_push(dataset)


    def dump(self, prefix='blackbox'):
        """
        Save the collected data to a file (Lines of JSON, seperated by \n)
        """
        filename = datetime.now().strftime("{}-%Y-%m-%d %H%M%S.jsonl".format(prefix))

        self.log.info("file dump: {}".format(filename))

        open(os.path.join(self.path, filename), 'w').writelines(self.record_lines)




    def csv_push(self, dataset):
        t = int(datetime.now().timestamp() / self.csv_config['interval'])

        if self.csv_interval_time is None:    # first start
            self.csv_interval_time = t
        elif self.csv_interval_time != t:
            self.csv_interval_time = t
            # print('minute')
            filename = datetime.now().strftime("%Y-%m-%d.csv")
            if not os.path.isfile(os.path.join(self.path, filename)):
                open(os.path.join(self.path, filename), 'a').write(";".join([col[0] for col in self.csv_config['columns']]) + '\n')

            row = []
            for col in self.csv_config['columns']:
                row.append(dictget(dataset, col[1:]))
            csv = ";".join(["{}".format('' if r is None else r) for r in row])

            open(os.path.join(self.path, filename), 'a').write(csv + '\n')




if __name__ == "__main__":
    box = Blackbox(path='blackbox', size=3)
    box.push({'t': 1})
    box.push({'t': 2})
    box.push({'t': 3})
    box.push({'t': 4})
    box.dump()

    # config = (('AAA', 'a', 0), ('BBB', 'b'), ('CCC', 'c', 'x'))
    # trc = CSVLog(config, interval_divider=5)
    #
    # while True:
    #     trc.push({'a': [1, 2, 3], 'b': 'hallo'})
    #
    #     time.sleep(0.1)

