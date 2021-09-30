import trio
import tractor

from wrath.net import create_send_sock
from wrath.net import create_recv_sock
from wrath.net import build_ipv4_packet
from wrath.net import build_tcp_packet
from wrath.net import unpack


@tractor.context
async def microsender(ctx: tractor.Context, target):
    # print('dbg! microsender: inside')
    await ctx.started()
    # print('dbg! microsender: called ctx.started()')
    ipv4_packet = build_ipv4_packet(target)
    send_sock = create_send_sock()
    # print('dbg! microsender: built ipv4 packet and send sock')
    # print('dbg! microsender: opening stream')
    async with ctx.open_stream() as stream:
        # print('dbg! microsender: opened stream')
        async for port in stream:
            # print('dbg! microsender: got port %d' % port)
            tcp_packet = build_tcp_packet(target, port)
            await send_sock.sendto(ipv4_packet + tcp_packet, (target, port))


@tractor.context
async def batchworker(ctx: tractor.Context, target):
    await ctx.started()
    # print('dbg! batchworker: inside')
    async with (
        tractor.open_nursery() as tn,
        ctx.open_stream() as parent_stream,
    ):
        # print('dbg! batchworker: starting streamer actor')
        p = await tn.start_actor('streamer {}'.format(__import__('random').randint(0, 100)), enable_modules=[__name__])
        # print('dbg! batchworker: started streamer actor')
        # print('dbg! batchworker: opening parent stream')
        # print('dbg! batchworker: about to loop over parent stream')
    
        async with (
                p.open_context(
                    microsender,
                    target=target,
                ) as (ctx2, _),

                ctx2.open_stream() as stream,
            ):
            # print('dbg! batchworker: opened parent stream')
            async for batch in parent_stream:
            # print('dbg! batchworker: inside async for loop, opening stream to microsender')
                # print('dbg! batchworker: inside async for loop, opened stream to microsender, about to send ports to microsender stream')
                for port in batch:
                    # print('dbg! batchworker: inside async for loop, opened stream to microsender, sending port %d to stream' % port)
                    await stream.send(port)       


async def receiver(target, task_status=trio.TASK_STATUS_IGNORED):
    # print('dbg! receiver: inside')
    task_status.started()
    # print('dbg! receiver: called task_status.started()')
    recv_sock = create_recv_sock(target)
    # print('dbg! receiver: created recv sock, about to bind')
    await recv_sock.bind(('enp5s0', 0x0800))
    # print('dbg! receiver: bound recv sock')
    while not recv_sock.is_readable():
        await trio.sleep(0.1)
    while True:
        # print('dbg! receiver: recv sock readable')
        # with trio.move_on_after(0.25) as cancel_scope:
        #     response = await recv_sock.recv(1024 * 16)
        # if cancel_scope.cancelled_caught:
        #     break
        response = await recv_sock.recv(1024 * 16)
        src, flags = unpack(response)
        if flags == 18:
            print('port %d: open' % src)
            yield src
        elif flags == 20:
            print('port %d: closed' % src)
            yield src


