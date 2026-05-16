{
  description = "Telegram media-to-GIF bot";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      lib = nixpkgs.lib;
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = lib.genAttrs systems;
      pkgsFor = system: import nixpkgs { inherit system; };

      makePackage = pkgs:
        let
          source = lib.cleanSourceWith {
            src = ./.;
            filter = path: type:
              let
                name = baseNameOf path;
              in
              !(name == ".env"
                || name == ".git"
                || name == "__pycache__"
                || name == "result"
                || name == "temp"
                || lib.hasSuffix ".pyc" (toString path));
          };
          pythonEnv = pkgs.python3.withPackages (ps: with ps; [
            aiogram
            loguru
          ]);
        in
        pkgs.stdenvNoCC.mkDerivation {
          pname = "poctikbot";
          version = "0.1.0";
          src = source;

          nativeBuildInputs = [ pkgs.makeWrapper ];

          dontBuild = true;

          installPhase = ''
            runHook preInstall

            install -Dm644 main.py $out/share/poctikbot/main.py
            makeWrapper ${pythonEnv}/bin/python $out/bin/poctikbot \
              --add-flags "$out/share/poctikbot/main.py" \
              --prefix PATH : ${lib.makeBinPath [ pkgs.ffmpeg ]}

            runHook postInstall
          '';
        };
    in
    {
      packages = forAllSystems (system:
        let
          pkgs = pkgsFor system;
        in
        rec {
          poctikbot = makePackage pkgs;
          default = poctikbot;
        });

      apps = forAllSystems (system: {
        poctikbot = {
          type = "app";
          program = "${self.packages.${system}.poctikbot}/bin/poctikbot";
        };
        default = self.apps.${system}.poctikbot;
      });

      devShells = forAllSystems (system:
        let
          pkgs = pkgsFor system;
          pythonEnv = pkgs.python3.withPackages (ps: with ps; [
            aiogram
            loguru
          ]);
        in
        {
          default = pkgs.mkShell {
            packages = [
              pythonEnv
              pkgs.ffmpeg
            ];
          };
        });

      formatter = forAllSystems (system: (pkgsFor system).nixpkgs-fmt);

      nixosModules.default = { config, lib, pkgs, ... }:
        let
          cfg = config.services.poctikbot;
        in
        {
          options.services.poctikbot = {
            enable = lib.mkEnableOption "PocTikBot Telegram media-to-GIF bot";

            package = lib.mkOption {
              type = lib.types.package;
              default = self.packages.${pkgs.stdenv.hostPlatform.system}.poctikbot;
              defaultText = lib.literalExpression "inputs.poctikbot.packages.\${pkgs.stdenv.hostPlatform.system}.poctikbot";
              description = "Package to run for the bot service.";
            };

            tokenFile = lib.mkOption {
              type = lib.types.nullOr lib.types.str;
              default = null;
              example = "/run/secrets/poctikbot-token";
              description = ''
                Path to a file containing only the Telegram bot token.
                The file is passed to the service as a systemd credential.
              '';
            };

            environmentFile = lib.mkOption {
              type = lib.types.nullOr lib.types.str;
              default = null;
              example = "/run/secrets/poctikbot.env";
              description = ''
                Optional environment file. It can define POCTIKBOT_TOKEN,
                POCTIKBOT_TOKEN_FILE, or POCTIKBOT_WORK_DIR.
              '';
            };

            workDir = lib.mkOption {
              type = lib.types.str;
              default = "/var/lib/poctikbot";
              description = "Directory used for temporary downloaded and rendered media.";
            };

            user = lib.mkOption {
              type = lib.types.str;
              default = "poctikbot";
              description = "User account that runs the bot service.";
            };

            group = lib.mkOption {
              type = lib.types.str;
              default = "poctikbot";
              description = "Group account that runs the bot service.";
            };
          };

          config = lib.mkIf cfg.enable {
            assertions = [
              {
                assertion = cfg.tokenFile != null || cfg.environmentFile != null;
                message = "services.poctikbot.tokenFile or services.poctikbot.environmentFile must be set.";
              }
            ];

            users.groups.${cfg.group} = { };
            users.users.${cfg.user} = {
              isSystemUser = true;
              group = cfg.group;
              home = cfg.workDir;
            };

            systemd.services.poctikbot = {
              description = "PocTikBot Telegram media-to-GIF bot";
              wantedBy = [ "multi-user.target" ];
              after = [ "network-online.target" ];
              wants = [ "network-online.target" ];

              environment = {
                POCTIKBOT_WORK_DIR = cfg.workDir;
              } // lib.optionalAttrs (cfg.tokenFile != null) {
                POCTIKBOT_TOKEN_FILE = "%d/telegram-token";
              };

              serviceConfig = {
                Type = "simple";
                ExecStart = "${cfg.package}/bin/poctikbot";
                Restart = "on-failure";
                RestartSec = "5s";

                User = cfg.user;
                Group = cfg.group;
                StateDirectory = "poctikbot";
                WorkingDirectory = cfg.workDir;
                ReadWritePaths = [ cfg.workDir ];

                NoNewPrivileges = true;
                PrivateTmp = true;
                ProtectHome = true;
                ProtectSystem = "strict";
              } // lib.optionalAttrs (cfg.tokenFile != null) {
                LoadCredential = [ "telegram-token:${cfg.tokenFile}" ];
              } // lib.optionalAttrs (cfg.environmentFile != null) {
                EnvironmentFile = cfg.environmentFile;
              };
            };
          };
        };
    };
}
