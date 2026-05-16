from aiogram import Dispatcher, F, Bot
from aiogram.types import Message, FSInputFile
from aiogram.filters import CommandStart
from aiogram.exceptions import TelegramEntityTooLarge, TelegramBadRequest
import asyncio
import os
from pathlib import Path
from loguru import logger

TOKEN_ENV = "POCTIKBOT_TOKEN"
TOKEN_FILE_ENV = "POCTIKBOT_TOKEN_FILE"
WORK_DIR_ENV = "POCTIKBOT_WORK_DIR"

dp = Dispatcher()


def file_ok(path: str):
    """Проверка, что файл существует и не пустой"""
    return os.path.exists(path) and os.path.getsize(path) > 0


def load_token() -> str:
    token = os.environ.get(TOKEN_ENV)
    if token:
        return token

    token_file = os.environ.get(TOKEN_FILE_ENV)
    if token_file:
        token = Path(token_file).read_text(encoding="utf-8").strip()
        if token:
            return token

    raise RuntimeError(f"set {TOKEN_ENV} or {TOKEN_FILE_ENV}")


def configure_work_dir() -> None:
    work_dir = Path(os.environ.get(WORK_DIR_ENV, ".")).expanduser()
    work_dir.mkdir(parents=True, exist_ok=True)
    os.chdir(work_dir)


@dp.message(CommandStart())
async def command_start(message: Message):
    await message.answer("пришли мне фото/видео и я тебе сделаю гифу")


# =======================
#      PHOTO → GIF
# =======================
@dp.message(F.photo)
async def photo_to_gif(message: Message, bot: Bot):
    logger.info(f"@{message.from_user.username} скинул фото")

    file_name = message.photo[-1].file_id
    jpg_path = f"{file_name}.jpg"
    mp4_path = f"{file_name}.mp4"
    gif_path = f"{file_name}.gif"

    # скачиваем
    await message.bot.download(message.photo[-1], destination=jpg_path)

    # -----------------------------
    # GIF для Telegram (mp4)
    # -----------------------------
    logger.info("Конвертация JPG → MP4")
    process_mp4 = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", jpg_path,
        "-t", "2",
        "-vf", "scale=512:-1:flags=lanczos,fps=30",
        "-movflags", "+faststart",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        mp4_path,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    await process_mp4.wait()

    if not file_ok(mp4_path):
        await message.reply("⚠️ Ошибка: не удалось создать mp4")
        return

    await message.reply_animation(
        FSInputFile(mp4_path),
        caption="*гифка для телеграма*",
        has_spoiler=True,
        parse_mode="MarkdownV2"
    )

    # -----------------------------
    # GIF для Discord (gif)
    # -----------------------------
    logger.info("Создание GIF через ffmpeg")

    process_gif = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", jpg_path,
        "-t", "2",
        "-vf", "scale=480:-1:flags=lanczos,fps=30",
        gif_path,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    await process_gif.wait()

    if not file_ok(gif_path):
        await message.reply("⚠️ Ошибка: GIF не создался")
        return

    await message.reply_animation(
        FSInputFile(gif_path),
        caption="*гифка для дискорда*\n_\\(блюр не работает, дуров почини телеграм\\)_",
        has_spoiler=True,
        parse_mode="MarkdownV2"
    )

    # cleanup
    for f in [jpg_path, mp4_path, gif_path]:
        if os.path.exists(f):
            os.remove(f)


# =======================
#      VIDEO → GIF
# =======================
@dp.message(F.video)
async def video_to_gif(message: Message, bot: Bot):
    logger.info(f"@{message.from_user.username} скинул видео")

    file_name = message.video.file_id
    mp4_in = f"{file_name}.mp4"
    mp4_out = f"{file_name}_done.mp4"
    gif_path = f"{file_name}.gif"

    try:
        await message.bot.download(message.video, destination=mp4_in)
    except TelegramBadRequest:
        await message.reply("видео слишком большое")
        return

    # -----------------------------
    # GIF для Telegram (mp4)
    # -----------------------------
    logger.info("Конвертация video → mp4 GIF")
    process_mp4 = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y",
        "-i", mp4_in,
        "-vf", "scale=512:-1:flags=lanczos,fps=60",
        "-movflags", "+faststart",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-an",
        mp4_out,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    await process_mp4.wait()

    if not file_ok(mp4_out):
        await message.reply("⚠️ Ошибка: mp4 для телеграма не создался")
        return

    await message.reply_animation(
        FSInputFile(mp4_out),
        caption="*гифка для телеграма*",
        has_spoiler=True,
        parse_mode="MarkdownV2"
    )

    # -----------------------------
    # GIF для Discord (gif)
    # -----------------------------
    logger.info("Конвертация video → gif")

    # палитра
    process_palette = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y",
        "-i", mp4_in,
        "-vf", "scale=480:-1:flags=lanczos,palettegen",
        "palette.png",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    await process_palette.wait()

    # сам GIF
    process_gif = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-i", mp4_in,
        "-i", "palette.png",
        "-lavfi", "scale=480:-1:flags=lanczos[x];[x][1:v]paletteuse",
        gif_path,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    await process_gif.wait()

    if file_ok(gif_path):
        try:
            await message.reply_animation(
                FSInputFile(gif_path),
                caption="*гифка для дискорда*\n_\\(блюр не работает, дуров почини телеграм\\)_",
                has_spoiler=True,
                parse_mode="MarkdownV2"
            )
        except TelegramEntityTooLarge:
            await message.reply("гифка для дискорда слишком большая")
    else:
        await message.reply("⚠️ Ошибка: GIF не создался")

    # cleanup
    for f in [mp4_in, mp4_out, gif_path, "palette.png"]:
        if os.path.exists(f):
            os.remove(f)


# =======================
#         MAIN
# =======================
async def main():
    token = load_token()
    configure_work_dir()
    logger.success("бот запущен!")
    await dp.start_polling(Bot(token=token))


if __name__ == "__main__":
    asyncio.run(main())
