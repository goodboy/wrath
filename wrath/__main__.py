import itertools
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
async def worker_pool(status, workers=4):
    async with tractor.open_nursery() as tn:
        portals = []
        tx, rx = trio.open_memory_channel(math.inf)

        for i in range(workers):
            portals.append(
                await tn.start_actor(
                    'worker {}'.format(i),
                    enable_modules=['wrath.core']
                )
            )

        async def _map(func, ports):
            async def send_result(func, portal, target, batch):
                await tx.send(await portal.run(func, target=target, batch=batch, status=status))

            async with trio.open_nursery() as n:
                await n.start(receiver, status)
                for batch, portal in zip(more_itertools.sliced(ports, len(ports) // workers), itertools.cycle(portals)):
                    n.start_soon(send_result, batchworker, portal, target, batch)
            
            for _ in range(len(ports)):
                yield await rx.receive()

        yield _map

        await tn.cancel()        


async def main(target, intervals) -> None:
    status = {
        port: {'sent': False, 'recv': False, 'retry': 0}
        for interval in intervals
        for port in range(*interval)
    }

    while True:
        ports = [port for port, info in status.items() if not info['recv'] and info['retry'] <= 3]
        if not ports:
            break
        async with worker_pool(status) as actor_map:
            async with aclosing(actor_map(batchworker, ports)) as results:
                async for message in results:
                    if message is None:
                        break


if __name__ == '__main__':
    target, intervals, ports = parse_args()
    trio.run(main, target, intervals)    