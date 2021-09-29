import trio

from wrath.net import create_send_sock
from wrath.net import create_recv_sock
from wrath.net import build_ipv4_packet
from wrath.net import build_tcp_packet
from wrath.net import unpack


async def batchworker(target, batch, status):
    ipv4_packet = build_ipv4_packet(target)
    async with trio.open_nursery() as nursery:
        limiter = trio.CapacityLimiter(2048)
        mutex = trio.Lock()
        for port in batch:
            async with limiter:
                await nursery.start(microsender, mutex, target, port, ipv4_packet, status)


async def receiver(status, *, task_status=trio.TASK_STATUS_IGNORED):
    task_status.started()
    recv_sock = create_recv_sock()
    await recv_sock.bind(('enp5s0', 0x0800))
    await trio.sleep(0.5)
    while True:
        with trio.move_on_after(0.25) as cancel_scope:
            response = await recv_sock.recv(1024 * 16)
        if cancel_scope.cancelled_caught:
            break
        src, flags = unpack(response)
        if flags == 18:
            print('port %d: open' % src)
            status[src]['recv'] = True
        elif flags == 20:
            # print('port %d: closed' % src)
            status[src]['recv'] = True


async def microsender(mutex, target, port, ipv4_packet, status, task_status=trio.TASK_STATUS_IGNORED):
    async with mutex:
        task_status.started()
        send_sock = create_send_sock()
        tcp_packet = build_tcp_packet(target, port)
        await send_sock.sendto(ipv4_packet + tcp_packet, (target, port))
        status[port]['sent'] = True
        status[port]['retry'] += 1
