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
        
        await tn.cancel()
 

# print('dbg! main: defined status dict')
# print('dbg! main: defining recv_from_receiver')
async def recv_from_receiver(stream, status, task_status=trio.TASK_STATUS_IGNORED):
    packets_received = 0
    # print('dbg! recv_from_receiver: inside')
    task_status.started()
    #print('dbg! recv_from_receiver: task_status.started()')
    async for port in stream:
        packets_received += 1
        print('packets received: %d' % packets_received)
        # print('dbg! recv_from_receiver: got a port %d' % port)
        status[port]['recv'] = True
        # print('dbg! recv_from_receiver: exiting %d' % port)



async def main(target, intervals, workers=4) -> None:
    # print('dbg! main: inside')
    status = {
        port: {'sent': False, 'recv': False, 'retry': 0}
        for interval in intervals
        for port in range(*interval)
    }

    # print('dbg! main: in front of big async with')
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
        await nursery.start(recv_from_receiver, recv_stream, status)
        # print('dbg! main: started recv_from_receiver')
        while True:
            # print('dbg! main: inside while True loop')
            ports = [port for port, info in status.items() if not info['recv']]
            print(not ports)
            if not ports:
                break
                # print('dbg! main: inside while True loop, no ports, breaking'
            for batch, stream in zip(more_itertools.sliced(ports, len(ports) // workers), itertools.cycle(streams)):
                # print('dbg! main: inside while True loop, insider for loop, sending to stream')
                await stream.send(batch)
    print('dbg! main: after big async with')

if __name__ == '__main__':
    target, intervals, ports = parse_args()
    trio.run(main, target, intervals)    