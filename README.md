# ☠️ SPECTRE Discord Bot

> **The official Discord bot for SPECTRE — Cybersecurity Club of IIT Bhilai.**  
> Built to power *The Lattice*, a campus-wide mystery & trading event run in collaboration with MERAZ.

---

## 📖 About

The SPECTRE bot handles everything for **The Lattice** event — from welcoming participants and distributing roles, to running a private trading ticket system and enforcing event rules. It is built with [discord.py](https://discordpy.readthedocs.io/) and uses slash-style prefix commands (`!`).

**Key features:**
- 🎟️ Private 1-on-1 trade ticket system (auto self-destructs after 5 minutes, logs saved)
- 🚪 Interactive role-claim button for entering The Lattice
- 📜 Automated rulebook and welcome embed delivery
- 🧹 Channel moderation (bulk message clearing)
- 📡 Bot health monitoring (latency check)

---

## ⚙️ Setup

1. Clone the repo and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Create a `.env` file in the project root:
   ```env
   TOKEN=your_discord_bot_token_here
   ```

3. Run the bot:
   ```bash
   python main.py
   ```

> **Note:** `.env` is git-ignored and must never be committed.

---

## 🤖 Commands

### 👥 Available to Everyone

| Command | Description |
|---------|-------------|
| `!trade` | Creates a **1-on-1 private trade ticket** embed in `#marketplace`. Another user clicks *"Claim Ticket"* to open a private channel with you. The channel auto-deletes after **5 minutes** and a full chat transcript is DM'd to both users. |
| `!help` | Displays all available commands and their required roles. |

> `!trade` can **only** be used inside the `#marketplace` channel.

---

### 🔒 Requires Role: `Group_Manager`

All commands below are restricted to members with the **Group_Manager** role. The invoking message is automatically deleted after any of these commands run.

| Command | Alias(es) | Description |
|---------|-----------|-------------|
| `!lattice` | — | Posts an embed with a **"Click to Enter The Lattice"** button. Users who click it receive the `LATTICE` role and are directed to `#init`. |
| `!welcome` | `!intro` | Sends the official **The Lattice** event welcome embed with the event banner image and a note about the `#marketplace` trading rule. |
| `!welcome_gen` | `!welcom_gen` | Sends the official **SPECTRE Cybersecurity Club** general welcome embed (hacker-themed, matrix green). |
| `!rules` | `!rulebook` | Sends the event **rulebook** (`rulebook.txt`) as a file attachment along with an embed highlighting key rules (team size, duration, trading rules, emergency protocol). |
| `!clear <number>` | `!purge <number>` | Deletes the last `n` messages in the current channel. Example: `!clear 10` |
| `!ping` | — | Shows the bot's **WebSocket latency** and **API round-trip latency**. |

---

## 🗂️ Project Structure

```
SPECTRE_DISCORD/
├── main.py            # Core bot logic & all commands
├── update_rules.py    # Utility script to update the rules command
├── requirements.txt   # Python dependencies
├── rulebook.txt       # Event rulebook (attached by !rules)
├── the_lattice.jpg    # Event banner image (attached by !welcome)
├── .env               # Bot token — NOT committed (git-ignored)
└── .gitignore
```

---

## 🛡️ Permissions & Role Hierarchy

```
Everyone  ──►  !trade, !help
Group_Manager  ──►  All commands above + !lattice, !welcome, !welcome_gen, !rules, !clear, !ping
```

The bot globally enforces this check on every command except `!trade` and `!help`.  
Unauthorized users receive an ephemeral error message that auto-deletes after 5 seconds.

---

## 👥 Credits

| Role | GitHub |
|------|--------|
| 💻 Developer | [@Ashux7](https://github.com/Ashux7) |
| 🎯 Club Coordinator | [@Arpit-Mohapatra007](https://github.com/Arpit-Mohapatra007) |

**SPECTRE — Cybersecurity Club, IIT Bhilai**
