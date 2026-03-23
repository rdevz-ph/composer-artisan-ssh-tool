import json
import os
import shutil
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import paramiko


class ComposerArtisanSSHApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Laravel Composer + Artisan SSH Tool")
        width = 980
        height = 860

        self.root.withdraw()
        self.root.update_idletasks()

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)

        self.root.geometry(f"{width}x{height}+{x}+{y}")
        self.root.minsize(900, 760)
        self.root.deiconify()

        appdata = os.getenv("APPDATA") or str(Path.home())
        app_folder = os.path.join(appdata, "ComposerArtisanTool")
        os.makedirs(app_folder, exist_ok=True)

        # Different app + different JSON file from the ZIP deploy tool
        self.config_file = os.path.join(app_folder, "composer_artisan_profiles.json")
        self._suspend_events = False

        self.host = tk.StringVar(value="example.com")
        self.username = tk.StringVar(value="example")
        self.domain_name = tk.StringVar(value="")
        self.quick_domain = tk.StringVar(value="[Main Domain]")
        self.profile_name = tk.StringVar(value="")
        self.command_group = tk.StringVar(value="composer")
        self.command_choice = tk.StringVar(value="composer install")
        self.custom_command = tk.StringVar(value="")
        self.status = tk.StringVar(value="Ready")

        self.data = {
            "last_profile": "",
            "profiles": {},
            "recent_domains": [],
        }

        self.state_file = os.path.join(app_folder, "app_state.json")
        self.state = {"disclaimer_shown": False}

        self.profile_combo: ttk.Combobox | None = None
        self.domain_combo: ttk.Combobox | None = None
        self.group_combo: ttk.Combobox | None = None
        self.command_combo: ttk.Combobox | None = None
        self.setup_agent_button: ttk.Button | None = None
        self.check_status_button: ttk.Button | None = None
        self.run_button: ttk.Button | None = None

        self.command_presets = {
            "composer": [
                "composer install",
                "composer install --no-dev",
                "composer install --no-dev -o",
                "composer diagnose",
                "composer update",
                "composer dump-autoload",
                "composer dump-autoload -o",
                "composer clear-cache",
            ],
            "artisan": [
                "php artisan optimize",
                "php artisan optimize:clear",
                "php artisan migrate",
                "php artisan migrate --force",
                "php artisan db:seed",
                "php artisan db:seed --force",
                "php artisan migrate --seed",
                "php artisan migrate --seed --force",
                "php artisan key:generate",
                "php artisan key:generate --force",
                "php artisan config:clear",
                "php artisan config:cache",
                "php artisan cache:clear",
                "php artisan route:clear",
                "php artisan route:cache",
                "php artisan view:clear",
                "php artisan view:cache",
                "php artisan queue:restart",
                "php artisan storage:link",
            ],
            "custom": [
                "[Use Custom Command Below]",
            ],
        }

        self._build_ui()
        self._load_config()
        self._load_state()
        self._bind_auto_save()
        self._refresh_command_choices()
        self._refresh_preview()
        self._show_disclaimer()

    def _load_state(self) -> None:
        if not os.path.exists(self.state_file):
            return

        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)

            if isinstance(loaded, dict):
                self.state["disclaimer_shown"] = loaded.get("disclaimer_shown", False)
        except Exception:
            pass

    def _save_state(self) -> None:
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=4)
        except Exception:
            pass

    def _show_disclaimer(self) -> None:
        if self.state.get("disclaimer_shown"):
            return

        dialog = tk.Toplevel(self.root)
        dialog.withdraw()
        dialog.title("Disclaimer")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        dialog.update_idletasks()

        width = 460
        height = 230

        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (width // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (height // 2)

        dialog.geometry(f"{width}x{height}+{x}+{y}")
        dialog.deiconify()

        ttk.Label(
            dialog,
            text="Disclaimer",
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w", padx=16, pady=(16, 8))

        ttk.Label(
            dialog,
            text=(
                "This tool is developed by Romel Brosas.\n\n"
                "Use at your own risk. The developer is not responsible for any damage.\n\n"
                "Always review commands before executing."
            ),
            justify="left",
            wraplength=420,
        ).pack(anchor="w", padx=16)

        btns = ttk.Frame(dialog)
        btns.pack(fill="x", padx=16, pady=16)

        def close_only() -> None:
            dialog.destroy()

        def dont_show_again() -> None:
            self.state["disclaimer_shown"] = True
            self._save_state()
            dialog.destroy()

        ttk.Button(btns, text="OK", command=close_only).pack(side="right")
        ttk.Button(btns, text="Don't Show Again", command=dont_show_again).pack(
            side="right", padx=(0, 8)
        )

        dialog.protocol("WM_DELETE_WINDOW", close_only)
        self.root.wait_window(dialog)

    def _build_ui(self) -> None:
        pad = {"padx": 12, "pady": 8}

        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True)

        title = ttk.Label(
            main,
            text="Laravel Composer + Artisan SSH Tool",
            font=("Segoe UI", 16, "bold"),
        )
        title.pack(anchor="w", **pad)

        desc = ttk.Label(
            main,
            text=(
                "Run Composer and Artisan commands directly over SSH for a selected domain. "
                "Choose a saved domain first, pick a preset command, or enter a custom command "
                "when needed."
            ),
            wraplength=900,
            justify="left",
        )
        desc.pack(anchor="w", padx=12)

        profile_box = ttk.LabelFrame(main, text="Profiles")
        profile_box.pack(fill="x", padx=12, pady=(8, 6))
        profile_box.columnconfigure(1, weight=1)

        ttk.Label(profile_box, text="Saved profile").grid(
            row=0, column=0, sticky="w", padx=(10, 8), pady=10
        )

        self.profile_combo = ttk.Combobox(
            profile_box,
            textvariable=self.profile_name,
            state="readonly",
        )
        self.profile_combo.grid(row=0, column=1, sticky="ew", pady=10)
        self.profile_combo.bind("<<ComboboxSelected>>", self._on_profile_selected)

        ttk.Button(profile_box, text="New Profile", command=self._new_profile).grid(
            row=0, column=2, padx=(8, 0), pady=10
        )

        ttk.Button(profile_box, text="Save / Update", command=self._save_profile).grid(
            row=0, column=3, padx=(8, 0), pady=10
        )

        ttk.Button(profile_box, text="Rename", command=self._rename_profile).grid(
            row=0, column=4, padx=(8, 0), pady=10
        )

        ttk.Button(profile_box, text="Delete", command=self._delete_profile).grid(
            row=0, column=5, padx=(8, 10), pady=10
        )

        backup_row = ttk.Frame(profile_box)
        backup_row.grid(
            row=1, column=0, columnspan=6, sticky="ew", padx=10, pady=(0, 10)
        )
        ttk.Button(
            backup_row, text="Backup Profiles", command=self._backup_profiles
        ).pack(side="left")
        ttk.Button(
            backup_row, text="Restore Profiles", command=self._restore_profiles
        ).pack(side="left", padx=(8, 0))

        form = ttk.Frame(main)
        form.pack(fill="x", padx=12, pady=12)
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="SSH username").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=6
        )
        ttk.Entry(form, textvariable=self.username).grid(
            row=0, column=1, columnspan=2, sticky="ew", pady=6
        )

        ttk.Label(form, text="Host").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=6
        )
        ttk.Entry(form, textvariable=self.host).grid(
            row=1, column=1, columnspan=2, sticky="ew", pady=6
        )

        ttk.Label(form, text="Domain name").grid(
            row=2, column=0, sticky="w", padx=(0, 8), pady=6
        )
        ttk.Entry(form, textvariable=self.domain_name).grid(
            row=2, column=1, columnspan=2, sticky="ew", pady=6
        )
        ttk.Label(
            form,
            text="Leave blank to use the main domain",
            foreground="#888888",
        ).grid(row=3, column=1, columnspan=2, sticky="w", pady=(0, 6))

        ttk.Label(form, text="Quick domain").grid(
            row=4, column=0, sticky="w", padx=(0, 8), pady=6
        )

        self.domain_combo = ttk.Combobox(
            form,
            textvariable=self.quick_domain,
            state="readonly",
        )
        self.domain_combo.grid(row=4, column=1, sticky="ew", pady=6)

        domain_btns = ttk.Frame(form)
        domain_btns.grid(row=4, column=2, sticky="ew", padx=(8, 0), pady=6)

        ttk.Button(
            domain_btns, text="Rename Domain", command=self._rename_quick_domain
        ).pack(side="left")

        ttk.Button(
            domain_btns, text="Delete Domain", command=self._delete_quick_domain
        ).pack(side="left", padx=(8, 0))

        self.domain_combo.bind("<<ComboboxSelected>>", self._on_quick_domain_selected)

        ttk.Label(
            form,
            text="Choose the target domain first before running a command",
            foreground="#888888",
        ).grid(row=5, column=1, columnspan=2, sticky="w", pady=(0, 8))

        ttk.Separator(form, orient="horizontal").grid(
            row=6, column=0, columnspan=3, sticky="ew", pady=10
        )

        ttk.Label(form, text="Command group").grid(
            row=7, column=0, sticky="w", padx=(0, 8), pady=6
        )
        self.group_combo = ttk.Combobox(
            form,
            textvariable=self.command_group,
            state="readonly",
            values=["composer", "artisan", "custom"],
        )
        self.group_combo.grid(row=7, column=1, columnspan=2, sticky="ew", pady=6)
        self.group_combo.bind("<<ComboboxSelected>>", self._on_command_group_changed)

        ttk.Label(form, text="Preset command").grid(
            row=8, column=0, sticky="w", padx=(0, 8), pady=6
        )
        self.command_combo = ttk.Combobox(
            form,
            textvariable=self.command_choice,
            state="readonly",
        )
        self.command_combo.grid(row=8, column=1, columnspan=2, sticky="ew", pady=6)
        self.command_combo.bind("<<ComboboxSelected>>", self._on_change)

        ttk.Label(form, text="Custom command").grid(
            row=9, column=0, sticky="w", padx=(0, 8), pady=6
        )
        ttk.Entry(form, textvariable=self.custom_command).grid(
            row=9, column=1, columnspan=2, sticky="ew", pady=6
        )

        ttk.Label(
            form,
            text="Examples: php artisan migrate --force  |  composer install --no-dev",
            foreground="#888888",
        ).grid(row=10, column=1, columnspan=2, sticky="w", pady=(0, 6))

        btns = ttk.Frame(main)
        btns.pack(fill="x", padx=12, pady=12)

        self.setup_agent_button = ttk.Button(
            btns,
            text="Setup SSH Agent",
            command=self._setup_ssh_agent,
        )
        self.setup_agent_button.pack(side="left")

        self.check_status_button = ttk.Button(
            btns,
            text="Check SSH Status",
            command=self._check_ssh_status,
        )
        self.check_status_button.pack(side="left", padx=(8, 0))

        self.run_button = ttk.Button(
            btns,
            text="Run Command",
            command=self._run_command,
        )
        self.run_button.pack(side="left", padx=(8, 0))

        ttk.Label(main, text="Command preview").pack(anchor="w", padx=12)
        self.output = tk.Text(main, height=8, wrap="word")
        self.output.pack(fill="both", expand=False, padx=12, pady=(6, 12))

        ttk.Label(main, text="Log").pack(anchor="w", padx=12)
        self.log = tk.Text(main, height=20, wrap="word")
        self.log.pack(fill="both", expand=True, padx=12, pady=(6, 12))

        ttk.Label(
            main,
            textvariable=self.status,
            relief="sunken",
            anchor="w",
        ).pack(fill="x", side="bottom")

    def _bind_auto_save(self) -> None:
        for var in (
            self.username,
            self.host,
            self.domain_name,
            self.command_group,
            self.command_choice,
            self.custom_command,
        ):
            var.trace_add("write", self._on_change)

    def _remote_target(self) -> str:
        domain = self.domain_name.get().strip().strip("/").replace("\\", "")
        return "~/public_html" if not domain else f"~/public_html/{domain}"

    def _effective_command(self) -> str:
        group = self.command_group.get().strip().lower()

        if group == "custom":
            return self.custom_command.get().strip()

        return self.command_choice.get().strip()

    def _build_preview_text(self) -> str:
        username = self.username.get().strip()
        host = self.host.get().strip()
        remote_dir = self._remote_target()
        command = self._effective_command()

        if not username or not host:
            return ""

        lines = [
            "SSH Command Steps:",
            f"1. Connect SSH to {username}@{host}",
            f"2. Change directory to: {remote_dir}",
        ]

        if command:
            lines.append(f"3. Run command: {command}")
        else:
            lines.append("3. No command selected yet")

        return "\n".join(lines)

    def _refresh_preview(self) -> None:
        preview = self._build_preview_text()
        self.output.delete("1.0", tk.END)
        if preview:
            self.output.insert("1.0", preview)

    def _append_log(self, text: str) -> None:
        self.log.insert(tk.END, text)
        self.log.see(tk.END)

    def _set_running_state(self, running: bool) -> None:
        state = "disabled" if running else "normal"

        if self.setup_agent_button is not None:
            self.setup_agent_button.config(state=state)
        if self.check_status_button is not None:
            self.check_status_button.config(state=state)
        if self.run_button is not None:
            self.run_button.config(state=state)
        if self.profile_combo is not None:
            self.profile_combo.config(state="disabled" if running else "readonly")
        if self.domain_combo is not None:
            self.domain_combo.config(state="disabled" if running else "readonly")
        if self.group_combo is not None:
            self.group_combo.config(state="disabled" if running else "readonly")
        if self.command_combo is not None:
            self.command_combo.config(state="disabled" if running else "readonly")

        self.root.config(cursor="wait" if running else "")

    def _pwsh_available(self) -> bool:
        return shutil.which("pwsh") is not None

    def _setup_ssh_agent(self) -> None:
        if not self._pwsh_available():
            messagebox.showerror(
                "PowerShell 7 not found",
                "pwsh was not found in PATH.\n\nInstall PowerShell 7 first, then try again.",
            )
            return

        key_path = str(Path.home() / ".ssh" / "id_rsa")
        key_path_ed25519 = str(Path.home() / ".ssh" / "id_ed25519")

        if os.path.exists(key_path_ed25519):
            selected_key = key_path_ed25519
        else:
            selected_key = key_path

        if not os.path.exists(selected_key):
            messagebox.showerror(
                "SSH Key Not Found",
                "No default SSH key was found.\n\n"
                "Expected one of these:\n"
                "~/.ssh/id_ed25519\n"
                "~/.ssh/id_rsa\n\n"
                "Generate a key first, then try again.",
            )
            return

        agent_cmd = (
            "Get-Service ssh-agent -ErrorAction SilentlyContinue | "
            "Where-Object {$_.Status -ne 'Running'} | "
            "Start-Service -ErrorAction SilentlyContinue; "
            "ssh-add -D; "
            f"ssh-add '{selected_key}'; "
            "ssh-add -l"
        )

        try:
            subprocess.Popen(
                ["pwsh", "-NoExit", "-Command", agent_cmd],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            self.status.set("Opened SSH Agent setup window")
            self._append_log(
                f"\n$ Opened PowerShell for SSH agent setup using key: {selected_key}\n"
            )
            messagebox.showinfo(
                "SSH Agent",
                "A PowerShell window was opened.\n\n"
                "Enter your SSH key passphrase there if prompted.\n"
                "After ssh-add succeeds, return here and retry SSH Status or Run Command.",
            )
        except Exception as exc:
            self.status.set("Failed to open SSH Agent setup")
            self._append_log(f"Error: {exc}\n")
            messagebox.showerror(
                "SSH Agent",
                f"Failed to open PowerShell for SSH agent setup.\n\n{exc}",
            )

    def _get_ssh_client(self) -> paramiko.SSHClient:
        username = self.username.get().strip()
        host = self.host.get().strip()

        if not username or not host:
            raise ValueError("SSH username and host are required.")

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(
            hostname=host,
            username=username,
            timeout=10,
            banner_timeout=10,
            auth_timeout=10,
            look_for_keys=True,
            allow_agent=True,
        )
        return client

    def _run_ssh_command(
        self, client: paramiko.SSHClient, command: str
    ) -> tuple[int, str, str]:
        _, stdout, stderr = client.exec_command(command)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode(errors="replace")
        err = stderr.read().decode(errors="replace")
        return exit_code, out, err

    def _quote_remote(self, value: str) -> str:
        # Quote paths safely for the remote shell, but preserve leading ~/ so
        # the remote shell can still expand it to the user's home directory.
        if value.startswith("~/"):
            rest = value[2:]
            return "~/" + "'" + rest.replace("'", "'\"'\"'") + "'"
        return "'" + value.replace("'", "'\"'\"'") + "'"

    def _check_ssh_status(self) -> None:
        if not self.username.get().strip() or not self.host.get().strip():
            messagebox.showwarning(
                "Missing fields",
                "Please fill in the SSH username and host first.",
            )
            return

        self._set_running_state(True)
        self.status.set("Checking SSH server status...")
        self._append_log(
            f"\n$ Checking SSH status for {self.username.get().strip()}@{self.host.get().strip()}\n"
        )

        threading.Thread(target=self._execute_ssh_status_check, daemon=True).start()

    def _execute_ssh_status_check(self) -> None:
        client = None
        try:
            client = self._get_ssh_client()
            _, stdout, stderr = client.exec_command("echo SSH_OK")
            output = stdout.read().decode(errors="replace").strip()
            err = stderr.read().decode(errors="replace").strip()

            if output:
                self.root.after(0, self._append_log, output + "\n")
            if err:
                self.root.after(0, self._append_log, err + "\n")

            self.root.after(0, lambda: self._set_running_state(False))

            if "SSH_OK" in output:
                self.root.after(0, self.status.set, "SSH server is alive and reachable")
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "SSH Status",
                        "Server is alive.\nSSH connection succeeded.",
                    ),
                )
            else:
                self.root.after(0, self.status.set, "SSH status check failed")
                self.root.after(
                    0,
                    lambda: messagebox.showerror(
                        "SSH Status",
                        "Connected, but did not receive expected SSH_OK response.",
                    ),
                )

        except Exception as exc:
            self.root.after(0, lambda: self._set_running_state(False))
            self.root.after(0, self.status.set, "SSH status check failed")
            self.root.after(0, self._append_log, f"Error: {exc}\n")
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "SSH Status",
                    "Server is not reachable, authentication failed, or your SSH key "
                    "passphrase is not loaded in ssh-agent.\n\n"
                    f"{exc}",
                ),
            )
        finally:
            if client is not None:
                client.close()

    def _run_command(self) -> None:
        username = self.username.get().strip()
        host = self.host.get().strip()
        command = self._effective_command()

        if not username or not host:
            messagebox.showwarning(
                "Missing fields",
                "Please fill in the SSH username and host first.",
            )
            return

        if not command:
            messagebox.showwarning(
                "No command",
                "Please select a preset command or enter a custom command.",
            )
            return

        self._remember_current_domain()
        self._save_config()
        self._set_running_state(True)
        self.status.set("Running remote command...")
        self._append_log("\n$ Starting remote command run\n")

        threading.Thread(target=self._execute_command, daemon=True).start()

    def _execute_command(self) -> None:
        client = None

        try:
            username = self.username.get().strip()
            host = self.host.get().strip()
            remote_dir = self._remote_target()
            command = self._effective_command()

            self.root.after(0, self.status.set, "Connecting via SSH...")
            self.root.after(
                0,
                self._append_log,
                f"Connecting to {username}@{host}...\n",
            )

            client = self._get_ssh_client()

            quoted_dir = self._quote_remote(remote_dir)
            full_command = f"cd {quoted_dir} && {command}"

            self.root.after(0, self.status.set, "Running command...")
            self.root.after(0, self._append_log, f"$ {full_command}\n\n")

            code, out, err = self._run_ssh_command(client, full_command)

            if out:
                self.root.after(
                    0, self._append_log, out if out.endswith("\n") else out + "\n"
                )
            if err:
                self.root.after(
                    0, self._append_log, err if err.endswith("\n") else err + "\n"
                )

            self.root.after(0, lambda: self._set_running_state(False))

            if code == 0:
                self.root.after(0, self.status.set, "Command finished successfully")
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "Success",
                        "Remote command completed successfully.",
                    ),
                )
            elif out.strip() or err.strip():
                self.root.after(
                    0,
                    self.status.set,
                    f"Command finished with warnings (exit code {code})",
                )
                self.root.after(
                    0,
                    lambda: messagebox.showwarning(
                        "Completed with Warnings",
                        f"The command produced output but returned exit code {code}.\n\n"
                        "Please review the log.",
                    ),
                )
            else:
                raise RuntimeError(f"Remote command failed with exit code {code}.")

        except Exception as exc:
            self.root.after(0, lambda: self._set_running_state(False))
            self.root.after(0, self.status.set, "Command failed")
            self.root.after(0, self._append_log, f"\nError: {exc}\n")
            self.root.after(
                0,
                lambda: messagebox.showerror(
                    "Error",
                    "Command failed.\n\n"
                    "If your SSH key is passphrase-protected, run Setup SSH Agent first.\n\n"
                    f"{exc}",
                ),
            )
        finally:
            if client is not None:
                client.close()

    def _refresh_command_choices(self) -> None:
        if self.command_combo is None:
            return

        group = self.command_group.get().strip().lower() or "composer"
        values = self.command_presets.get(group, [])
        self.command_combo["values"] = values

        current = self.command_choice.get().strip()
        if current not in values:
            self.command_choice.set(values[0] if values else "")

    def _on_command_group_changed(self, event=None) -> None:
        group = self.command_group.get().strip().lower()

        self._suspend_events = True
        try:
            if group != "custom":
                self.custom_command.set("")
        finally:
            self._suspend_events = False

        self._refresh_command_choices()
        self._refresh_preview()
        self._save_config()

    def _on_change(self, *args) -> None:
        if self._suspend_events:
            return
        self._refresh_preview()
        self._save_config()

    def _remember_current_domain(self) -> None:
        domain = self.domain_name.get().strip()
        domain_label = "[Main Domain]" if not domain else domain

        domains = self.data.setdefault("recent_domains", [])
        cleaned_domains = []
        seen = set()

        for item in domains:
            value = str(item).strip()
            if not value:
                continue
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned_domains.append(value)

        domains = cleaned_domains

        existing_index = next(
            (
                i
                for i, item in enumerate(domains)
                if item.lower() == domain_label.lower()
            ),
            None,
        )
        if existing_index is not None:
            domains.pop(existing_index)

        domains.insert(0, domain_label)
        self.data["recent_domains"] = domains[:20]
        self._refresh_domain_dropdown()

    def _refresh_profile_dropdown(self) -> None:
        if self.profile_combo is None:
            return

        names = sorted(self.data.get("profiles", {}).keys(), key=str.lower)
        self.profile_combo["values"] = names

        current = self.profile_name.get().strip()
        if current and current not in names:
            self.profile_name.set("")

    def _refresh_domain_dropdown(self) -> None:
        if self.domain_combo is None:
            return

        domains = []
        seen = set()

        for item in self.data.get("recent_domains", []):
            value = str(item).strip()
            if not value:
                continue
            key = value.lower()
            if key in seen:
                continue
            seen.add(key)
            domains.append(value)

        for profile in self.data.get("profiles", {}).values():
            profile_domain = str(profile.get("domain", "")).strip()
            domain_label = "[Main Domain]" if not profile_domain else profile_domain
            key = domain_label.lower()
            if key not in seen:
                seen.add(key)
                domains.append(domain_label)

        if "[Main Domain]".lower() not in seen:
            domains.insert(0, "[Main Domain]")

        self.domain_combo["values"] = domains

    def _clear_form_fields(self) -> None:
        self._suspend_events = True
        try:
            self.host.set("")
            self.username.set("")
            self.domain_name.set("")
            self.quick_domain.set("[Main Domain]")
            self.command_group.set("composer")
            self.command_choice.set("composer install")
            self.custom_command.set("")
        finally:
            self._suspend_events = False

        self._refresh_command_choices()
        self._refresh_preview()
        self._save_config()

    def _new_profile(self) -> None:
        self.profile_name.set("")
        self.data["last_profile"] = ""
        self._clear_form_fields()
        self.status.set("Ready for new profile")

    def _on_profile_selected(self, event=None) -> None:
        name = self.profile_name.get().strip()
        profile = self.data.get("profiles", {}).get(name)
        if not profile:
            return

        self._suspend_events = True
        try:
            self.host.set(profile.get("host", ""))
            self.username.set(profile.get("username", ""))
            self.domain_name.set(profile.get("domain", ""))
            self.command_group.set(profile.get("command_group", "composer"))
            self.command_choice.set(profile.get("command_choice", "composer install"))
            self.custom_command.set(profile.get("custom_command", ""))
            self.quick_domain.set(
                "[Main Domain]"
                if not profile.get("domain", "").strip()
                else profile.get("domain", "").strip()
            )
        finally:
            self._suspend_events = False

        self.data["last_profile"] = name
        self._remember_current_domain()
        self._refresh_command_choices()
        self._refresh_preview()
        self._save_config()
        self.status.set(f'Loaded profile: "{name}"')

    def _on_quick_domain_selected(self, event=None) -> None:
        value = self.quick_domain.get().strip()
        self.domain_name.set("" if value == "[Main Domain]" else value)
        self.status.set("Quick domain applied")

    def _save_profile(self) -> None:
        name = self.profile_name.get().strip()
        if not name:
            name = (
                simpledialog.askstring(
                    "Save Profile",
                    "Enter profile name:",
                    parent=self.root,
                )
                or ""
            )

        name = name.strip()
        if not name:
            return

        self.data.setdefault("profiles", {})[name] = {
            "host": self.host.get().strip(),
            "username": self.username.get().strip(),
            "domain": self.domain_name.get().strip(),
            "command_group": self.command_group.get().strip(),
            "command_choice": self.command_choice.get().strip(),
            "custom_command": self.custom_command.get().strip(),
        }

        self.profile_name.set(name)
        self.data["last_profile"] = name
        self._remember_current_domain()
        self._refresh_profile_dropdown()
        self._save_config()
        self.status.set(f'Profile saved: "{name}"')
        messagebox.showinfo("Saved", f'Profile "{name}" saved successfully.')

    def _rename_profile(self) -> None:
        old_name = self.profile_name.get().strip()
        if not old_name:
            messagebox.showwarning("No profile", "Please select a profile to rename.")
            return

        profiles = self.data.get("profiles", {})
        if old_name not in profiles:
            messagebox.showwarning("Missing profile", "Selected profile was not found.")
            return

        new_name = simpledialog.askstring(
            "Rename Profile",
            "Enter new profile name:",
            initialvalue=old_name,
            parent=self.root,
        )
        if new_name is None:
            return

        new_name = new_name.strip()
        if not new_name:
            messagebox.showwarning("Invalid name", "Profile name cannot be blank.")
            return

        if new_name != old_name and new_name in profiles:
            messagebox.showwarning(
                "Duplicate profile",
                f'Profile "{new_name}" already exists.',
            )
            return

        profiles[new_name] = profiles.pop(old_name)
        self.profile_name.set(new_name)

        if self.data.get("last_profile") == old_name:
            self.data["last_profile"] = new_name

        self._refresh_profile_dropdown()
        self._save_config()
        self.status.set(f'Profile renamed to: "{new_name}"')
        messagebox.showinfo("Renamed", f'Profile renamed to "{new_name}".')

    def _backup_profiles(self) -> None:
        backup_path = filedialog.asksaveasfilename(
            title="Backup Profiles",
            defaultextension=".json",
            initialfile="composer_artisan_profiles_backup.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not backup_path:
            return

        try:
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "last_profile": self.data.get("last_profile", ""),
                        "profiles": self.data.get("profiles", {}),
                        "recent_domains": self.data.get("recent_domains", []),
                    },
                    f,
                    indent=4,
                )
            self.status.set("Profiles backup created")
            messagebox.showinfo(
                "Backup Complete", "Profiles backup saved successfully."
            )
        except Exception as exc:
            self.status.set("Profiles backup failed")
            messagebox.showerror("Backup Failed", f"Failed to save backup.\n\n{exc}")

    def _restore_profiles(self) -> None:
        restore_path = filedialog.askopenfilename(
            title="Restore Profiles",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not restore_path:
            return

        if not messagebox.askyesno(
            "Restore Profiles",
            "This will replace your current saved profiles and recent domains.\n\nContinue?",
        ):
            return

        try:
            with open(restore_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)

            if not isinstance(loaded, dict):
                raise ValueError("Backup file format is invalid.")

            profiles = loaded.get("profiles", {})
            recent_domains = loaded.get("recent_domains", [])
            last_profile = loaded.get("last_profile", "")

            if not isinstance(profiles, dict):
                raise ValueError("Backup profiles data is invalid.")
            if not isinstance(recent_domains, list):
                raise ValueError("Backup recent_domains data is invalid.")

            self.data["profiles"] = profiles
            self.data["recent_domains"] = recent_domains
            self.data["last_profile"] = (
                last_profile if isinstance(last_profile, str) else ""
            )

            self._refresh_profile_dropdown()
            self._refresh_domain_dropdown()

            restored_last = self.data.get("last_profile", "").strip()
            if restored_last and restored_last in self.data.get("profiles", {}):
                self.profile_name.set(restored_last)
                self._on_profile_selected()
            else:
                self._new_profile()

            self._save_config()
            self.status.set("Profiles restored successfully")
            messagebox.showinfo("Restore Complete", "Profiles restored successfully.")
        except Exception as exc:
            self.status.set("Profiles restore failed")
            messagebox.showerror(
                "Restore Failed", f"Failed to restore backup.\n\n{exc}"
            )

    def _delete_profile(self) -> None:
        name = self.profile_name.get().strip()
        if not name:
            messagebox.showwarning("No profile", "Please select a profile to delete.")
            return

        profiles = self.data.get("profiles", {})
        profile = profiles.get(name)
        if not profile:
            messagebox.showwarning("Missing profile", "Selected profile was not found.")
            return

        if not messagebox.askyesno("Delete Profile", f'Delete profile "{name}"?'):
            return

        deleted_domain = str(profile.get("domain", "")).strip()
        deleted_domain_label = "[Main Domain]" if not deleted_domain else deleted_domain

        profiles.pop(name, None)

        if self.data.get("last_profile") == name:
            self.data["last_profile"] = ""

        still_used = False
        for other_profile in profiles.values():
            other_domain = str(other_profile.get("domain", "")).strip()
            other_domain_label = "[Main Domain]" if not other_domain else other_domain
            if other_domain_label.lower() == deleted_domain_label.lower():
                still_used = True
                break

        if not still_used:
            recent_domains = self.data.get("recent_domains", [])
            self.data["recent_domains"] = [
                item
                for item in recent_domains
                if str(item).strip().lower() != deleted_domain_label.lower()
            ]

        self.profile_name.set("")

        current_domain = self.domain_name.get().strip()
        self.quick_domain.set("[Main Domain]" if not current_domain else current_domain)

        self._refresh_profile_dropdown()
        self._refresh_domain_dropdown()
        self._save_config()
        self._refresh_preview()
        self.status.set(f'Profile deleted: "{name}"')

    def _load_config(self) -> None:
        if not os.path.exists(self.config_file):
            self._refresh_profile_dropdown()
            self._refresh_domain_dropdown()
            return

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)

            if isinstance(loaded, dict):
                self.data["last_profile"] = loaded.get("last_profile", "")
                self.data["profiles"] = loaded.get("profiles", {})
                self.data["recent_domains"] = loaded.get("recent_domains", [])

            self._refresh_profile_dropdown()
            self._refresh_domain_dropdown()

            last_profile = self.data.get("last_profile", "").strip()
            if last_profile and last_profile in self.data.get("profiles", {}):
                self.profile_name.set(last_profile)
                self._on_profile_selected()
            else:
                current_domain = self.domain_name.get().strip()
                self.quick_domain.set(
                    "[Main Domain]" if not current_domain else current_domain
                )

        except Exception as exc:
            self.status.set(f"Failed to load config: {exc}")
            self._refresh_profile_dropdown()
            self._refresh_domain_dropdown()

    def _save_config(self) -> None:
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "last_profile": self.data.get("last_profile", ""),
                        "profiles": self.data.get("profiles", {}),
                        "recent_domains": self.data.get("recent_domains", []),
                    },
                    f,
                    indent=4,
                )
        except Exception as exc:
            self.status.set(f"Failed to save config: {exc}")

    def _rename_quick_domain(self) -> None:
        selected = self.quick_domain.get().strip()

        if not selected:
            messagebox.showwarning("No domain", "Please select a domain to rename.")
            return

        if selected == "[Main Domain]":
            messagebox.showwarning(
                "Not allowed", "You cannot rename the Main Domain option."
            )
            return

        new_name = simpledialog.askstring(
            "Rename Domain",
            "Enter new domain name:",
            initialvalue=selected,
            parent=self.root,
        )

        if new_name is None:
            return

        new_name = new_name.strip().strip("/").replace("\\", "")
        if not new_name:
            messagebox.showwarning("Invalid name", "Domain name cannot be blank.")
            return

        if new_name.lower() == "[main domain]".lower():
            messagebox.showwarning("Invalid name", "That domain name is reserved.")
            return

        all_domains = [str(d).strip() for d in self.data.get("recent_domains", [])]
        for profile in self.data.get("profiles", {}).values():
            profile_domain = str(profile.get("domain", "")).strip()
            if profile_domain:
                all_domains.append(profile_domain)

        if new_name.lower() != selected.lower():
            for domain in all_domains:
                if domain.lower() == new_name.lower():
                    messagebox.showwarning(
                        "Duplicate domain", f'Domain "{new_name}" already exists.'
                    )
                    return

        self.data["recent_domains"] = [
            new_name if str(d).strip().lower() == selected.lower() else d
            for d in self.data.get("recent_domains", [])
        ]

        for profile in self.data.get("profiles", {}).values():
            if str(profile.get("domain", "")).strip().lower() == selected.lower():
                profile["domain"] = new_name

        if self.domain_name.get().strip().lower() == selected.lower():
            self.domain_name.set(new_name)

        self.quick_domain.set(new_name)
        self._refresh_domain_dropdown()
        self._save_config()
        self.status.set(f'Domain renamed to: "{new_name}"')
        messagebox.showinfo("Renamed", f'Domain renamed to "{new_name}".')

    def _delete_quick_domain(self) -> None:
        selected = self.quick_domain.get().strip()

        if not selected:
            messagebox.showwarning("No domain", "Please select a domain to delete.")
            return

        if selected == "[Main Domain]":
            messagebox.showwarning(
                "Not allowed", "You cannot delete the Main Domain option."
            )
            return

        if not messagebox.askyesno(
            "Delete Domain", f'Delete "{selected}" from quick domains?'
        ):
            return

        self.data["recent_domains"] = [
            d
            for d in self.data.get("recent_domains", [])
            if str(d).strip().lower() != selected.lower()
        ]

        for _, profile in self.data.get("profiles", {}).items():
            if str(profile.get("domain", "")).strip().lower() == selected.lower():
                profile["domain"] = ""

        if self.domain_name.get().strip().lower() == selected.lower():
            self.domain_name.set("")
            self.quick_domain.set("[Main Domain]")

        self._refresh_domain_dropdown()
        self._save_config()
        self.status.set(f'Domain removed: "{selected}"')

        messagebox.showinfo(
            "Deleted", f'Domain "{selected}" has been removed successfully.'
        )


if __name__ == "__main__":
    root = tk.Tk()

    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass

    app = ComposerArtisanSSHApp(root)
    root.mainloop()
