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

    def __init__(self, size, path=''):
        self.path = path
        self.log = logging.getLogger('blackbox')
        self.record_lines = []
        self.size = size
        os.makedirs(path, exist_ok=True)

    def push(self, dataset):
        """
        Convert dataset to JSON, append \n and append to FIFO list. Limit the size to maximum.
        :param dataset: dictionary
        """
        self.record_lines.append(json.dumps(dataset) + '\n')
        self.record_lines = self.record_lines[-self.size:]  # limit to latest


    def dump(self, prefix='blackbox'):
        """
        Save the collected data to a file (Lines of JSON, seperated by \n)
        """
        filename = datetime.now().strftime("{}-%Y-%m-%d %H%M%S.jsonl".format(prefix))

        self.log.info("file dump: {}".format(filename))

        open(os.path.join(self.path, filename), 'w').writelines(self.record_lines)



if __name__ == "__main__":
    box = Blackbox(path='blackbox', size=3)
    box.push({'t': 1})
    box.push({'t': 2})
    box.push({'t': 3})
    box.push({'t': 4})
    box.dump()
