import itertools
import functools
import math
import contextlib

import more_itertools
import trio
import tractor
from async_generator import aclosing

from wrath.cli import parse_args
from wrath.core import batchworker
from wrath.core import receiver


async def runner(func, portals, target, batch, workers=4):
    async with trio.open_nursery() as n:
        for batch, portal in zip(more_itertools.sliced(batch, len(batch) // workers), itertools.cycle(portals)):
            n.start_soon(functools.partial(portal.run, func, target=target, batch=batch))
    print('exiting runner')

@contextlib.asynccontextmanager
async def create_portals(workers=4):
    async with tractor.open_nursery() as tn:

        portals = []

        for i in range(workers):
            portals.append(
                await tn.start_actor(
                    'worker {}'.format(i),
                    enable_modules=['wrath.core']
                )
            )
                
        yield portals
        
        await tn.cancel(hard_kill=True)
 

async def main(target, intervals, workers=4) -> None:
    print('hit main')
    status = {
        port: {'sent': False, 'recv': False, 'retry': 0}
        for interval in intervals
        for port in range(*interval)
    }

    ports = [port for port in status.keys()]

    async with create_portals() as portals:
        await runner(batchworker, portals, target, ports)

    print('exiting main')

if __name__ == '__main__':
    target, intervals, ports = parse_args()
    trio.run(main, target, intervals)    