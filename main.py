from aiogram import Dispatcher, F, Bot
from aiogram.types import Message, FSInputFile
from aiogram.filters import CommandStart
from aiogram.exceptions import TelegramEntityTooLarge, TelegramBadRequest
import asyncio
import os
import tempfile
from pathlib import Path
from loguru import logger

TOKEN_ENV = "POCTIKBOT_TOKEN"
TOKEN_FILE_ENV = "POCTIKBOT_TOKEN_FILE"
WORK_DIR_ENV = "POCTIKBOT_WORK_DIR"

dp = Dispatcher()


def file_ok(path: str | Path):
    """Проверка, что файл существует и не пустой"""
    return os.path.exists(path) and os.path.getsize(path) > 0


async def run_ffmpeg(*args: str) -> bool:
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-hide_banner",
        "-y",
        *args,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()

    if process.returncode != 0:
        logger.error(
            "ffmpeg failed with code {}: {}",
            process.returncode,
            stderr.decode("utf-8", errors="replace").strip(),
        )
        return False

    return True


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

    with tempfile.TemporaryDirectory(prefix="photo-", dir=Path.cwd()) as temp_dir:
        temp_path = Path(temp_dir)
        jpg_path = temp_path / "input.jpg"
        mp4_path = temp_path / "telegram.mp4"
        gif_path = temp_path / "discord.gif"

        # скачиваем
        await message.bot.download(message.photo[-1], destination=jpg_path)

        # -----------------------------
        # GIF для Telegram (mp4)
        # -----------------------------
        logger.info("Конвертация JPG → MP4")
        mp4_ok = await run_ffmpeg(
            "-loop", "1",
            "-i", str(jpg_path),
            "-t", "2",
            "-vf", "scale=512:-2:flags=lanczos,fps=30",
            "-movflags", "+faststart",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            str(mp4_path),
        )

        if mp4_ok and file_ok(mp4_path):
            try:
                await message.reply_animation(
                    FSInputFile(mp4_path),
                    caption="*гифка для телеграма*",
                    has_spoiler=True,
                    parse_mode="MarkdownV2"
                )
            except (TelegramEntityTooLarge, TelegramBadRequest):
                await message.reply("⚠️ mp4 для телеграма создался, но не отправился")
        else:
            await message.reply("⚠️ Ошибка: не удалось создать mp4")

        # -----------------------------
        # GIF для Discord (gif)
        # -----------------------------
        logger.info("Создание GIF через ffmpeg")

        gif_ok = await run_ffmpeg(
            "-loop", "1",
            "-i", str(jpg_path),
            "-t", "2",
            "-vf", "scale=480:-2:flags=lanczos,fps=30",
            str(gif_path),
        )

        if not gif_ok or not file_ok(gif_path):
            await message.reply("⚠️ Ошибка: GIF не создался")
            return

        await message.reply_animation(
            FSInputFile(gif_path),
            caption="*гифка для дискорда*\n_\\(блюр не работает, дуров почини телеграм\\)_",
            has_spoiler=True,
            parse_mode="MarkdownV2"
        )


# =======================
#      VIDEO → GIF
# =======================
@dp.message(F.video)
async def video_to_gif(message: Message, bot: Bot):
    logger.info(f"@{message.from_user.username} скинул видео")

    with tempfile.TemporaryDirectory(prefix="video-", dir=Path.cwd()) as temp_dir:
        temp_path = Path(temp_dir)
        mp4_in = temp_path / "input.mp4"
        mp4_out = temp_path / "telegram.mp4"
        gif_path = temp_path / "discord.gif"
        palette_path = temp_path / "palette.png"

        try:
            await message.bot.download(message.video, destination=mp4_in)
        except TelegramBadRequest:
            await message.reply("видео слишком большое")
            return

        # -----------------------------
        # GIF для Telegram (mp4)
        # -----------------------------
        logger.info("Конвертация video → mp4 GIF")
        mp4_ok = await run_ffmpeg(
            "-i", str(mp4_in),
            "-vf", "scale=512:-2:flags=lanczos,fps=60",
            "-movflags", "+faststart",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-an",
            str(mp4_out),
        )

        if mp4_ok and file_ok(mp4_out):
            try:
                await message.reply_animation(
                    FSInputFile(mp4_out),
                    caption="*гифка для телеграма*",
                    has_spoiler=True,
                    parse_mode="MarkdownV2"
                )
            except (TelegramEntityTooLarge, TelegramBadRequest):
                await message.reply("⚠️ mp4 для телеграма создался, но не отправился")
        else:
            await message.reply("⚠️ Ошибка: mp4 для телеграма не создался")

        # -----------------------------
        # GIF для Discord (gif)
        # -----------------------------
        logger.info("Конвертация video → gif")

        # палитра
        palette_ok = await run_ffmpeg(
            "-i", str(mp4_in),
            "-vf", "scale=480:-2:flags=lanczos,palettegen",
            str(palette_path),
        )

        if not palette_ok or not file_ok(palette_path):
            await message.reply("⚠️ Ошибка: палитра GIF не создалась")
            return

        # сам GIF
        gif_ok = await run_ffmpeg(
            "-i", str(mp4_in),
            "-i", str(palette_path),
            "-lavfi", "scale=480:-2:flags=lanczos[x];[x][1:v]paletteuse",
            str(gif_path),
        )

        if file_ok(gif_path) and gif_ok:
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
