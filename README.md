# poctikbot

Telegram bot that turns photos and videos into Telegram/Discord GIF-style outputs.

## Configuration

The bot reads configuration from environment variables:

- `POCTIKBOT_TOKEN` - Telegram bot token.
- `POCTIKBOT_TOKEN_FILE` - path to a file containing the Telegram bot token.
- `POCTIKBOT_WORK_DIR` - directory for temporary media files, defaults to the current directory.

For local Docker runs, copy `.env.example` to `.env` and set the real token.

## Nix

Run directly:

```sh
POCTIKBOT_TOKEN=... nix run
```

Open a development shell with Python dependencies and `ffmpeg`:

```sh
nix develop
```

Use the NixOS module from another flake:

```nix
{
  inputs.poctikbot.url = "path:/path/to/poctikbot";

  outputs = { nixpkgs, poctikbot, ... }: {
    nixosConfigurations.host = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        poctikbot.nixosModules.default
        {
          services.poctikbot = {
            enable = true;
            tokenFile = "/run/secrets/poctikbot-token";
          };
        }
      ];
    };
  };
}
```
