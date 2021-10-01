import trio
import tractor

from wrath.net import create_send_sock
from wrath.net import create_recv_sock
from wrath.net import build_ipv4_packet
from wrath.net import build_tcp_packet
from wrath.net import unpack


async def microsender(target, port, ipv4_packet):
    # print('dbg! microsender: inside')
    # await ctx.started()
    # print('dbg! microsender: called ctx.started()')
    # print('dbg! microsender: built ipv4 packet and send sock')
    # print('dbg! microsender: opening stream')
    #async with ctx.open_stream() as stream:
        # print('dbg! microsender: opened stream')
        # print('dbg! microsender: got port %d' % port)
    send_sock = create_send_sock()
    tcp_packet = build_tcp_packet(target, port)
    await send_sock.sendto(ipv4_packet + tcp_packet, (target, port))


@tractor.context
async def batchworker(ctx: tractor.Context, target):
    # print('dbg! batchworker: inside')
    await ctx.started()
    ipv4_packet = build_ipv4_packet(target)

    async with (
        trio.open_nursery() as n,
        ctx.open_stream() as parent_stream,
    ):
        limiter = trio.CapacityLimiter(4096)
        async for batch in parent_stream:
            for port in batch:
                async with limiter:
                    n.start_soon(microsender, target, port, ipv4_packet)


async def receiver(target, task_status=trio.TASK_STATUS_IGNORED):
    task_status.started()
    status = {
        port: {'sent': False, 'recv': False, 'retry': 0}
        for port in range(65535)
    }
    recv_sock = create_recv_sock(target)
    await recv_sock.bind(('enp5s0', 0x0800))
    yield status
    while not recv_sock.is_readable():
        await trio.sleep(0.1)
    while True:
        with trio.move_on_after(0.25) as cancel_scope:
            response = await recv_sock.recv(1024 * 16)
        if cancel_scope.cancelled_caught:
            # print('cancel scope caught')
            yield {k: v for k, v in status.items() if not v['recv']}
        src, flags = unpack(response)
        if flags == 18:
            print('port %d: open' % src)
            status[src]['recv'] = True
        elif flags == 20:
            # print('port %d: closed' % src)
            status[src]['recv'] = True
    



