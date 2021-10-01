import itertools
import functools
import contextlib

import more_itertools
import trio
import tractor

from wrath.cli import parse_args
from wrath.core import batchworker
from wrath.core import receiver


async def runner(func, portals, target, batch, workers=4):
    async with trio.open_nursery() as n:
        for batch, portal in zip(more_itertools.sliced(batch, len(batch) // workers), itertools.cycle(portals)):
            n.start_soon(functools.partial(portal.run, func, target=target, batch=batch))


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

        portals.append(await tn.start_actor('recv_from_receiver', enable_modules=['wrath.core']))
                
        yield portals
        
        await tn.cancel(hard_kill=True)
 

async def main(target, workers=4) -> None:
    async with (
        trio.open_nursery() as nursery,

        create_portals() as portals,

        portals[0].open_context(batchworker, target=target) as (ctx0, _),
        portals[1].open_context(batchworker, target=target) as (ctx1, _),
        portals[2].open_context(batchworker, target=target) as (ctx2, _),
        portals[3].open_context(batchworker, target=target) as (ctx3, _),

        ctx0.open_stream() as stream0,
        ctx1.open_stream() as stream1,
        ctx2.open_stream() as stream2,
        ctx3.open_stream() as stream3,


        portals[4].open_stream_from(receiver, target=target) as recv_stream,
    ):
        streams = [stream0, stream1, stream2, stream3]
        # print('dbg! main: inside big async with')
        # print('dbg! main: starting recv_from_receiver')
        # print('dbg! main: started recv_from_receiver')

        async for status_update in recv_stream:
            # print('new status update')
            ports = [port for port, info in status_update.items() if not info['recv']]
            # print(len(ports))
            if not ports:
                break
            for batch, stream in zip(more_itertools.sliced(ports, len(ports) // workers), itertools.cycle(streams)):
                await stream.send(batch)


if __name__ == '__main__':
    target, intervals, ports = parse_args()
    trio.run(main, target)    