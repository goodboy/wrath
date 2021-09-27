import argparse
import math

from wrath.util import is_interval, to_interval
from wrath.util import is_port, to_port


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--batch-size', '-b', required=True, type=int)
    parser.add_argument('--port', '-p', required=True, action='append', nargs='*')
    parser.add_argument('target')

    args = parser.parse_args()

    target = args.target
    batch_size = args.batch_size

    ports = []
    intervals = []

    for arg in args.port:
        if is_port(arg[0]):
            ports.append(to_port(arg[0]))
        elif is_interval(arg[0]):
            intervals.append(to_interval(arg[0]))

    sliced_intervals = []

    for interval in intervals:
        if isinstance(interval, tuple):
            start, end = interval
        interval_length = len(range(start, end))
        if interval_length > batch_size:
            for index in range(math.ceil(interval_length / batch_size)):
                if index == interval_length // batch_size:
                    sliced_interval = (start, end + 1)  # end is inclusive
                else:
                    sliced_interval = (start, start + batch_size)
                    start += batch_size
                sliced_intervals.append(sliced_interval)
        else:
            sliced_intervals.append(interval)

    return target, sliced_intervals, ports