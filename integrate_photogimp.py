#!/usr/bin/env python3
"""
Integrador PhotoGIMP + GIMP
Permite integrar as personalizações do PhotoGIMP:
1. No GIMP instalado localmente (Flatpak ou Nativo)
2. No repositório de código-fonte do GIMP (gimp-source)
3. Criar patches e backups automatizados
"""

import os
import sys
import shutil
import subprocess
import argparse
from datetime import datetime
from pathlib import Path

WORKSPACE_DIR = Path(__file__).resolve().parent
PHOTOGIMP_DIR = WORKSPACE_DIR / "photogimp"
GIMP_SOURCE_DIR = WORKSPACE_DIR / "gimp-source"
PHOTOGIMP_CONFIG_SRC = PHOTOGIMP_DIR / ".config" / "GIMP" / "3.0"
PHOTOGIMP_LOCAL_SRC = PHOTOGIMP_DIR / ".local" / "share"

def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)

def detect_local_gimp_configs():
    """Detect potential GIMP 3 config directories."""
    home = Path.home()
    configs = []
    
    # Flatpak config
    flatpak_cfg = home / ".var" / "app" / "org.gimp.GIMP" / "config" / "GIMP" / "3.0"
    configs.append(("Flatpak (org.gimp.GIMP)", flatpak_cfg, True))
    
    # Native config
    native_cfg = home / ".config" / "GIMP" / "3.0"
    configs.append(("Nativo (~/.config/GIMP/3.0)", native_cfg, False))
    
    return configs

def backup_directory(dest_dir: Path) -> Path:
    """Creates a timestamped backup of the destination directory if it exists."""
    if dest_dir.exists() and any(dest_dir.iterdir()):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = dest_dir.parent / f"GIMP-backup-{timestamp}"
        print(f"[+] Criando backup de {dest_dir} em {backup_path}...")
        shutil.copytree(dest_dir, backup_path / dest_dir.name)
        return backup_path
    return None

def apply_to_local_gimp(target_type="all"):
    """Applies PhotoGIMP settings to local GIMP installations."""
    print_header("Aplicando PhotoGIMP na instalação local do GIMP")
    
    if not PHOTOGIMP_CONFIG_SRC.exists():
        print(f"[-] Erro: Diretório de origem {PHOTOGIMP_CONFIG_SRC} não encontrado.")
        return False

    configs = detect_local_gimp_configs()
    applied_count = 0
    home = Path.home()

    for name, cfg_dir, is_flatpak in configs:
        if target_type == "flatpak" and not is_flatpak:
            continue
        if target_type == "native" and is_flatpak:
            continue

        try:
            print(f"\n[>] Processando {name} -> {cfg_dir}")
            cfg_dir.mkdir(parents=True, exist_ok=True)
            backup_directory(cfg_dir)

            # Copy configs
            for item in PHOTOGIMP_CONFIG_SRC.iterdir():
                dest_item = cfg_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dest_item, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest_item)
            print(f"[✓] Configurações aplicadas com sucesso em {cfg_dir}")

            # If Flatpak, install desktop and icons
            if is_flatpak and PHOTOGIMP_LOCAL_SRC.exists():
                desktop_src = PHOTOGIMP_LOCAL_SRC / "applications" / "org.gimp.GIMP.desktop"
                desktop_dst = home / ".local" / "share" / "applications" / "org.gimp.GIMP.desktop"
                if desktop_src.exists():
                    desktop_dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(desktop_src, desktop_dst)
                    print(f"[✓] Launcher Desktop instalado em {desktop_dst}")

                icons_src = PHOTOGIMP_LOCAL_SRC / "icons"
                icons_dst = home / ".local" / "share" / "icons"
                if icons_src.exists():
                    icons_dst.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(icons_src, icons_dst, dirs_exist_ok=True)
                    print(f"[✓] Ícones instalados em {icons_dst}")

            applied_count += 1
        except PermissionError as e:
            print(f"[!] Permissão negada ao acessar {cfg_dir}: {e}")
        except Exception as e:
            print(f"[!] Erro ao aplicar em {cfg_dir}: {e}")

    return applied_count > 0

def apply_to_gimp_source():
    """Integrates PhotoGIMP presets into gimp-source tree."""
    print_header("Integrando PhotoGIMP na árvore de código-fonte (gimp-source)")
    
    if not GIMP_SOURCE_DIR.exists():
        print(f"[-] Erro: Diretório {GIMP_SOURCE_DIR} não encontrado.")
        return False

    target_profile_dir = GIMP_SOURCE_DIR / "data" / "photogimp-profile"
    print(f"[+] Criando diretório de perfil integrado: {target_profile_dir}")
    target_profile_dir.mkdir(parents=True, exist_ok=True)

    # Copy full config package to data/photogimp-profile
    if PHOTOGIMP_CONFIG_SRC.exists():
        for item in PHOTOGIMP_CONFIG_SRC.iterdir():
            dest_item = target_profile_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dest_item, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dest_item)
        print(f"[✓] Perfil e configurações do PhotoGIMP copiados para {target_profile_dir}")

    # Copy splashes
    splash_src = PHOTOGIMP_CONFIG_SRC / "splashes"
    if splash_src.exists():
        splash_dst = GIMP_SOURCE_DIR / "data" / "splashes" / "photogimp"
        splash_dst.mkdir(parents=True, exist_ok=True)
        shutil.copytree(splash_src, splash_dst, dirs_exist_ok=True)
        print(f"[✓] Splash screens sincronizadas para {splash_dst}")

    # Backup & update default sessionrc/toolrc in etc/
    etc_dir = GIMP_SOURCE_DIR / "etc"
    if etc_dir.exists():
        # Export photogimp sessionrc and toolrc as defaults reference
        shutil.copy2(PHOTOGIMP_CONFIG_SRC / "sessionrc", etc_dir / "sessionrc.photogimp")
        shutil.copy2(PHOTOGIMP_CONFIG_SRC / "toolrc", etc_dir / "toolrc.photogimp")
        if (PHOTOGIMP_CONFIG_SRC / "shortcutsrc").exists():
            shutil.copy2(PHOTOGIMP_CONFIG_SRC / "shortcutsrc", etc_dir / "shortcutsrc.photogimp")
        print(f"[✓] Arquivos de referência PhotoGIMP exportados para {etc_dir}/ (*.photogimp)")

    return True

def status_report():
    """Reports status of repositories and local installations."""
    print_header("Status dos Repositórios e Instalações")
    print(f"Workspace: {WORKSPACE_DIR}")
    print(f"- PhotoGIMP repo: {'[OK]' if PHOTOGIMP_DIR.exists() else '[FALTANDO]'}")
    print(f"- GIMP Source repo: {'[OK]' if GIMP_SOURCE_DIR.exists() else '[FALTANDO]'}")
    
    configs = detect_local_gimp_configs()
    for name, cfg_dir, _ in configs:
        exists = cfg_dir.exists()
        print(f"- {name}: {'[DETECTADO]' if exists else '[NÃO CRIADO AINDA]'} -> {cfg_dir}")

def main():
    parser = argparse.ArgumentParser(description="Integrador PhotoGIMP + GIMP")
    parser.add_argument("--status", action="store_true", help="Mostra o status atual")
    parser.add_argument("--apply-local", choices=["all", "flatpak", "native"], nargs="?", const="all", help="Aplica no GIMP instalado localmente")
    parser.add_argument("--apply-source", action="store_true", help="Integra no código-fonte gimp-source")
    parser.add_argument("--all", action="store_true", help="Executa todas as integrações (local e source)")

    args = parser.parse_args()

    if len(sys.argv) == 1 or args.status:
        status_report()
        if len(sys.argv) == 1:
            print("\nExecute com '--apply-source', '--apply-local' ou '--all' para aplicar as integrações.")
        return

    if args.all or args.apply_source:
        apply_to_gimp_source()

    if args.all or args.apply_local:
        target = args.apply_local if args.apply_local else "all"
        apply_to_local_gimp(target)

if __name__ == "__main__":
    main()
