import tractor
import trio

from wrath.cli import parse_args
from wrath.core import jumboworker


async def main() -> None:
    target, intervals, ports = parse_args()
    async with tractor.open_nursery() as nursery:
        actors = []
        for i in range(len(intervals)):
            actors.append(await nursery.start_actor('jumboworker {}'.format(i), enable_modules=['wrath.core']))       
        for actor, interval in zip(actors, intervals):
            await actor.run(jumboworker, target=target, interval=interval)
        for actor in actors:
            await actor.cancel_actor()


if __name__ == '__main__':
    trio.run(main)