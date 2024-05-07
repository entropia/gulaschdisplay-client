import asyncio
import json
import os
import shutil

import aiohttp
import subprocess
from contextlib import suppress
from i3ipc.aio.connection import Connection
from getmac import get_mac_address as gma

CURR_CONF = None


async def periodic(interval_sec, coro_name, *args, **kwargs):
    while True:
        with suppress(Exception):
            await coro_name(*args, **kwargs)
        await asyncio.sleep(interval_sec)


async def register():
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url=f"https://display.gulas.ch/control/{gma().capitalize()}/register",
            json={},
        ) as resp:
            ...


async def prepare_filesystem():
    shutil.rmtree("/tmp/chromium_userdata")
    os.mkdir("/tmp/chromium_userdata")


async def update_displays():
    i3 = await Connection().connect()

    for output in await i3.get_outputs():
        payload = {"name": output.name, "modes": [o.__dict__ for o in output.modes]}
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url=f"https://display.gulas.ch/control/{gma().capitalize()}/displays",
                json=payload,
            ) as resp:
                ...


async def configure(conf):
    i3 = await Connection().connect()
    subprocess.run(["killall", "chromium"])

    for dis in conf["displays"]:
        if dis["name"] not in await i3.get_outputs():
            pass
        print(f"configuring display {dis['name']}")

        c = await i3.command(f"output {dis['name']} transform {dis['rotation']}")

        mode = dis["mode"]
        if mode:
            c = await i3.command(
                f"output {dis['name']} mode {mode['width']}x{mode['height']}@{str(mode['refresh'])[:1]}Hz"
            )

        c = await i3.command(f"workspace \"{dis['name']}\" output {dis['name']}")
        print(c[0].ipc_data)

        c = await i3.command(f"workspace \"{dis['name']}\"")
        print(c[0].ipc_data)

        c = await i3.command(f"seat seat0 hide_cursor 3000")
        print(c[0].ipc_data)

        c = await i3.command(
            f"assign [title='^Chromium.*{dis['name']}.*'] \"{dis['name']}\""
        )
        print(c[0].ipc_data)

        if dis["url"]:
            c = await i3.command(
                f"exec chromium --noerrdialogs --enable-features=OverlayScrollbar --disable-restore-session-state --user-data-dir=/tmp/chromium_userdata/{dis['name']} --kiosk {dis['url']}"
            )
            print(c[0].ipc_data)

        await asyncio.sleep(0.5)


async def pull_config(force_update=False):
    async with aiohttp.ClientSession() as session:
        async with session.get(
            url=f"https://display.gulas.ch/control/{gma().capitalize()}/config",
        ) as resp:
            if resp.status != 200:
                return
            conf_response = await resp.json()
            global CURR_CONF
            if conf_response != CURR_CONF or force_update:
                await configure(conf=conf_response)
                CURR_CONF = conf_response


async def async_main():
    await asyncio.create_task(register())
    await asyncio.create_task(update_displays())
    await asyncio.create_task(pull_config(force_update=True))
    await asyncio.create_task(periodic(5, pull_config))


def main():
    loop = asyncio.get_event_loop().create_task(async_main())
    with suppress(KeyboardInterrupt):
        asyncio.get_event_loop().run_forever()
