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
async def open_actor_cluster(workers=4) -> list[tractor.Portal]:

    portals = []
    async with tractor.open_nursery() as tn:
        for i in range(workers):
            portals.append(
                await tn.start_actor(
                    'worker {}'.format(i),
                    enable_modules=['wrath.core']
                )
            )

        portals.append(await tn.start_actor('recv_from_receiver', enable_modules=['wrath.core']))
        yield tn, portals
        await tn.cancel()


# print('dbg! main: defined status dict')
# print('dbg! main: defining recv_from_receiver')
_maybe_retransmit = trio.Event()

async def recv_from_receiver(
    portal,
    status,
    task_status=trio.TASK_STATUS_IGNORED,
):
    global _maybe_retransmit

    async with portal.open_stream_from(receiver, target=target) as recv_stream:
        packets_received = 0
        # print('dbg! recv_from_receiver: inside')
        task_status.started()
        #print('dbg! recv_from_receiver: task_status.started()')
        # while status:
        # async for port in recv_stream:
        while True:
            with trio.move_on_after(0.69) as cs:
                # we exit here when this task is cancelled by the parent
                port = await recv_stream.receive()
                _maybe_retransmit.set()
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

    async with open_actor_cluster() as (tn, portals):
        async with (

            portals[0].open_context(batchworker, target=target) as (ctx0, _),
            portals[1].open_context(batchworker, target=target) as (ctx1, _),
            portals[2].open_context(batchworker, target=target) as (ctx2, _),
            portals[3].open_context(batchworker, target=target) as (ctx3, _),

            ctx0.open_stream() as stream0,
            ctx1.open_stream() as stream1,
            ctx2.open_stream() as stream2,
            ctx3.open_stream() as stream3,


        ):
            global _maybe_retransmit
            streams = [stream0, stream1, stream2, stream3]
            async with trio.open_nursery() as nursery:
                await nursery.start(
                    recv_from_receiver,
                    portals[4],
                    status,
                )

                # first cycle of batch sends
                ports = [port for port, info in status.items() if not info['recv']]

                async def send_batches(ps):
                    for batch, stream in zip(
                        more_itertools.sliced(ps, len(ps) // workers),
                        itertools.cycle(streams)
                    ):
                        # print('dbg! main: inside while True loop, insider for loop, sending to stream')
                        await stream.send(batch)

                await send_batches(ports)

                # wait for receiver to tell us it hit a delay in receiving packets
                await _maybe_retransmit.wait()
                _maybe_retransmit = trio.Event()

                # re-transmit loop
                repeats = 0
                last_ports = ports = [port for port, info in status.items() if not info['recv']]
                while True:
                    _maybe_retransmit = trio.Event()
                    await send_batches(ports)
                    await _maybe_retransmit.wait()

                    ports = [port for port, info in status.items() if not info['recv']]
                    print(f'remaining ports: {ports}')

                    if not ports:
                        print('we dun, all portz scanned')
                        break

                    if ports == last_ports:
                        print('ports were same as last re-transmitty')
                        if repeats > 2:
                            print(f'these ports failed bruv: {ports}')
                            break

                        repeats += 1

                    last_ports = ports

                # tear down the receiver task
                print('all ports were scanned bby, u win')
                nursery.cancel_scope.cancel()

                await tn.cancel()


if __name__ == '__main__':
    target, intervals, ports = parse_args()
    trio.run(main, target, intervals)    
