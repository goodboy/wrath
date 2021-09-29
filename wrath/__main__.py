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


@contextlib.asynccontextmanager
async def worker_pool(portals, status, workers=4):
    async def runner(func, ports):
        async def run(func, portal, target, batch, task_status=trio.TASK_STATUS_IGNORED):
            task_status.started()
            await portal.run(func, target=target, batch=batch, status=status)

        async with trio.open_nursery() as n:
            await n.start(receiver, status, target)
            for batch, portal in zip(more_itertools.sliced(ports, len(ports) // workers), itertools.cycle(portals)):
                n.start_soon(run, batchworker, portal, target, batch)
        
    yield runner


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
 

async def main(target, intervals) -> None:
    status = {
        port: {'sent': False, 'recv': False, 'retry': 0}
        for interval in intervals
        for port in range(*interval)
    }

    async with create_portals() as portals:
        while True:
            ports = [port for port, info in status.items() if not info['recv'] and info['retry'] <= 3]
            if not ports:
                break
            async with worker_pool(portals, status) as pool:
                await pool(batchworker, ports)


if __name__ == '__main__':
    target, intervals, ports = parse_args()
    trio.run(main, target, intervals)    