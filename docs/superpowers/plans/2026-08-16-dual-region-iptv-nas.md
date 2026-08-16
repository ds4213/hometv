# Dual-Region IPTV NAS Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the current `Guovin/iptv-api` Docker image on the US NAS every 12 hours to produce a US-tested playlist and a mainland-preserving playlist, then publish only guardrail-approved outputs to the permanent HomeTV paths.

**Architecture:** Pull `guovern/iptv-api:latest` once at the start of each scheduled cycle, record its resolved image identity, and run that exact local image twice as isolated, one-shot profiles without a second pull. The US profile performs quick playback/speed testing; the mainland profile collects and normalizes without using US playback failure as deletion evidence. A repository-owned Python orchestrator invokes both profiles, validates outputs through `hometv.live`, commits only approved generated artifacts, and uses fast-forward-only pushes.

**Tech Stack:** `guovern/iptv-api:latest`, Docker Compose, Python 3.12 standard library, POSIX shell, Git, Synology Task Scheduler.

## Global Constraints

- Phase 1 from `2026-08-16-curated-wanger-fongmi-live.md` is merged and proven on the N1 before NAS output can replace either seeded automatic playlist.
- Pull `guovern/iptv-api:latest` exactly once before each scheduled generation cycle.
- Abort the cycle if pull or image inspection fails; never replace a playlist after an uncertain image update.
- Run both regional profiles with `--pull never` after inspection so one cycle cannot mix two image versions.
- Record the resolved image ID and RepoDigest in both live health reports and the dry-run output.
- Track only explicit subscription URLs in this repository; `iptv-api` itself is not a channel source.
- Run two isolated profiles; do not share output, cache, or configuration directories.
- US profile prefers IPv4 and uses quick playback/speed testing.
- Mainland profile prefers IPv4, disables playback/speed filtering, and preserves sources that may be region-blocked from the US.
- Both runs are one-shot; the NAS scheduler owns the 12-hour interval.
- Publish through `publish_playlist`; never copy generator output directly over a stable playlist.
- A rejected output leaves the prior playlist byte-for-byte unchanged.
- Automatic commits may include only `vendor/live/auto-us.m3u`, `vendor/live/auto-cn.m3u`, `health/live-us.json`, and `health/live-cn.json`.
- Never force-push; never store GitHub or Gitee passwords, tokens, SSH private keys, cookies, or media credentials in the repository.
- Gitee automatic push is disabled by default and requires a repository-scoped credential plus explicit activation.
- Do not add scheduled GitHub Actions to a fork of `Guovin/iptv-api`; scheduling runs on the US NAS.

---

## File Structure

- Create `ops/iptv-api/compose.yaml`: `latest` image and two one-shot services.
- Create `ops/iptv-api/profiles/us/config/*`: US test profile, channel template, and explicit subscriptions.
- Create `ops/iptv-api/profiles/cn/config/*`: mainland-preserving profile, channel template, and explicit subscriptions.
- Create `ops/iptv-api/.gitignore`: profile output/cache exclusion.
- Create `hometv/nas.py`: subprocess orchestration, generated-path allowlist, clean-worktree checks, and safe Git publication.
- Create `scripts/nas_refresh.py`: dry-run/publish CLI.
- Create `ops/iptv-api/run.sh`: scheduler entry point.
- Create `tests/test_nas.py`: Docker-command and Git-scope behavior with mocks.
- Create `ops/iptv-api/README.md`: Synology deployment, dry run, scheduling, credentials, logs, image traceability, and rollback.

### Task 1: Latest-Image Dual-Profile Container Definition

**Files:**
- Create: `ops/iptv-api/compose.yaml`
- Create: `ops/iptv-api/.gitignore`
- Create: `ops/iptv-api/profiles/us/config/config.ini`
- Create: `ops/iptv-api/profiles/cn/config/config.ini`
- Create: `ops/iptv-api/profiles/us/config/user_demo.txt`
- Create: `ops/iptv-api/profiles/cn/config/user_demo.txt`
- Create: `ops/iptv-api/profiles/us/config/subscribe.txt`
- Create: `ops/iptv-api/profiles/cn/config/subscribe.txt`
- Create empty support files in both profile config directories: `alias.txt`, `blacklist.txt`, `whitelist.txt`, `local.txt`, and `epg.txt`.

**Interfaces:**
- Produces Compose services `iptv-us` and `iptv-cn`.
- Produces US output at `ops/iptv-api/profiles/us/output/ipv4/result.m3u`.
- Produces CN output at `ops/iptv-api/profiles/cn/output/ipv4/result.m3u`.

- [ ] **Step 1: Create the latest-image Compose definition**

```yaml
name: hometv-iptv

x-iptv-api: &iptv-api
  image: guovern/iptv-api:latest
  entrypoint: ["/bin/sh", "-lc"]
  command: [". /iptv-api/.venv/bin/activate && exec python -u /iptv-api/main.py"]
  network_mode: bridge
  restart: "no"

services:
  iptv-us:
    <<: *iptv-api
    volumes:
      - ./profiles/us/config:/iptv-api/config
      - ./profiles/us/output:/iptv-api/output
  iptv-cn:
    <<: *iptv-api
    volumes:
      - ./profiles/cn/config:/iptv-api/config
      - ./profiles/cn/output:/iptv-api/output
```

- [ ] **Step 2: Create the US one-shot configuration**

```ini
[Settings]
open_update = True
update_interval = 0
update_times =
update_startup = True
time_zone = America/Los_Angeles
source_file = config/user_demo.txt
final_file = output/result.txt
open_realtime_write = False
open_service = False
open_local = False
open_subscribe = True
open_auto_disable_source = False
open_history = True
open_m3u_result = True
open_url_info = False
open_epg = True
open_subscribe_epg = False
open_unmatch_category = False
output_urls_limit = 3
open_speed_test = True
speed_test_mode = quick
quick_test_target = 2
open_filter_resolution = True
open_filter_speed = True
min_resolution = 1280x720
min_speed = 0.2
performance_mode = balance
speed_test_timeout = 8
request_timeout = 10
ipv6_support = False
ipv_type = ipv4
ipv_type_prefer = ipv4
open_rtmp = False
```

- [ ] **Step 3: Create the mainland-preserving one-shot configuration**

```ini
[Settings]
open_update = True
update_interval = 0
update_times =
update_startup = True
time_zone = Asia/Shanghai
source_file = config/user_demo.txt
final_file = output/result.txt
open_realtime_write = False
open_service = False
open_local = False
open_subscribe = True
open_auto_disable_source = False
open_history = True
open_m3u_result = True
open_url_info = False
open_epg = True
open_subscribe_epg = False
open_unmatch_category = True
output_urls_limit = 5
open_speed_test = False
speed_test_mode = manual
open_filter_resolution = False
open_filter_speed = False
performance_mode = powersave
request_timeout = 15
ipv6_support = False
ipv_type = ipv4
ipv_type_prefer = ipv4
open_rtmp = False
```

- [ ] **Step 4: Track the explicit subscriptions and channel template**

Put these exact two lines in both `subscribe.txt` files:

```text
https://raw.githubusercontent.com/Kimentanm/aptv/refs/heads/master/m3u/iptv.m3u
http://82.156.243.185:33389/fwc.m3u
```

Put this template in both `user_demo.txt` files; `open_unmatch_category = True` preserves additional subscription channels:

```text
央视频道,#genre#
CCTV-1,
CCTV-2,
CCTV-3,
CCTV-4,
CCTV-5,
CCTV-5+,
CCTV-6,
CCTV-7,
CCTV-8,
CCTV-9,
CCTV-10,
CCTV-11,
CCTV-12,
CCTV-13,
CCTV-14,
CCTV-15,
CCTV-16,
CCTV-17,
卫视频道,#genre#
湖南卫视,
浙江卫视,
江苏卫视,
东方卫视,
北京卫视,
广东卫视,
深圳卫视,
安徽卫视,
山东卫视,
湖北卫视,
```

- [ ] **Step 5: Exclude runtime state**

Before adding `.gitignore`, create zero-byte `alias.txt`, `blacklist.txt`, `whitelist.txt`, `local.txt`, and `epg.txt` under both `profiles/us/config` and `profiles/cn/config`. These satisfy the generator's expected config layout without adding unreviewed subscriptions or filters.

```gitignore
profiles/*/output/
profiles/*/config/cache/
profiles/*/config/frozen.pkl
profiles/*/config/*.db
```

- [ ] **Step 6: Validate, pull, and inspect the current image**

```powershell
docker compose -f ops/iptv-api/compose.yaml config
docker compose -f ops/iptv-api/compose.yaml pull iptv-us
docker image inspect guovern/iptv-api:latest --format '{{json .Id}} {{json .RepoDigests}}'
```

Expected: Compose resolves both services; one current image is pulled; inspection prints a non-empty image ID and at least one RepoDigest. Both services resolve to `guovern/iptv-api:latest`.

- [ ] **Step 7: Commit**

```powershell
git add ops/iptv-api/compose.yaml ops/iptv-api/.gitignore ops/iptv-api/profiles
git commit -m "Add latest-image IPTV generator profiles"
```

### Task 2: Testable NAS Orchestration

**Files:**
- Create: `hometv/nas.py`
- Create: `scripts/nas_refresh.py`
- Create: `tests/test_nas.py`

**Interfaces:**
- Produces: `NasError(RuntimeError)`.
- Produces: `GeneratorRun(image_id: str, repo_digests: tuple[str, ...], us_path: Path, cn_path: Path)`.
- Produces: `RunResult(profile: str, input_path: Path, accepted: bool, channel_count: int, sha256: str)`.
- Produces: `run_generators(root: Path, runner: Callable = subprocess.run) -> GeneratorRun`.
- Produces: `publish_generated(root: Path, generated: GeneratorRun) -> list[RunResult]`.
- Produces: `commit_generated(root: Path, runner: Callable = subprocess.run) -> bool`.
- Produces CLI: `python scripts/nas_refresh.py --dry-run` and `python scripts/nas_refresh.py --publish`.

- [ ] **Step 1: Write failing command and publication-scope tests**

```python
def make_playlist(count: int, include_cn_groups: bool = True) -> bytes:
    names = [f"频道{i:02d}" for i in range(count)]
    groups = ["综合频道"] * count
    if include_cn_groups and count:
        names[0], groups[0] = "CCTV-1", "央视频道"
    if include_cn_groups and count > 1:
        names[1], groups[1] = "湖南卫视", "卫视频道"
    lines = ["#EXTM3U"]
    for index, (name, group) in enumerate(zip(names, groups)):
        lines.extend([f'#EXTINF:-1 group-title="{group}",{name}', f"https://media.example/{index}.m3u8"])
    return ("\n".join(lines) + "\n").encode()

def write_output(root: Path, profile: str, raw: bytes) -> Path:
    path = root / f"ops/iptv-api/profiles/{profile}/output/ipv4/result.m3u"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return path

def generator_runner(root: Path) -> Mock:
    def run(command, **kwargs):
        if command[:3] == ["docker", "image", "inspect"]:
            output = '{"Id":"sha256:image123","RepoDigests":["guovern/iptv-api@sha256:digest123"]}'
            return CompletedProcess(command, 0, output, "")
        if "run" in command and command[-1] == "iptv-us":
            write_output(root, "us", make_playlist(24))
        elif "run" in command and command[-1] == "iptv-cn":
            write_output(root, "cn", make_playlist(24))
        return CompletedProcess(command, 0, "", "")
    return Mock(side_effect=run)

def seed_stable_playlists(root: Path) -> None:
    for profile in ("us", "cn"):
        path = root / f"vendor/live/auto-{profile}.m3u"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(make_playlist(24))

def git_runner() -> Mock:
    def run(command, **kwargs):
        if command[:3] == ["git", "status", "--porcelain"]:
            return CompletedProcess(command, 0, "", "")
        if command[:3] == ["git", "diff", "--name-only"]:
            changed = "vendor/live/auto-us.m3u\nvendor/live/auto-cn.m3u\nhealth/live-us.json\nhealth/live-cn.json\n"
            return CompletedProcess(command, 0, changed, "")
        if command[:3] == ["git", "diff", "--cached"] and "--quiet" in command:
            return CompletedProcess(command, 1, "", "")
        return CompletedProcess(command, 0, "", "")
    return Mock(side_effect=run)

class NasTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_pulls_once_then_runs_both_profiles_without_another_pull(self):
        runner = generator_runner(self.root)
        generated = run_generators(self.root, runner=runner)
        commands = [call.args[0] for call in runner.call_args_list]
        self.assertEqual(commands[0][-2:], ["pull", "iptv-us"])
        self.assertEqual(commands[1][:3], ["docker", "image", "inspect"])
        self.assertEqual(commands[2][-5:], ["run", "--pull", "never", "--rm", "iptv-us"])
        self.assertEqual(commands[3][-5:], ["run", "--pull", "never", "--rm", "iptv-cn"])
        self.assertEqual(generated.image_id, "sha256:image123")
        self.assertEqual(generated.repo_digests, ("guovern/iptv-api@sha256:digest123",))
        self.assertTrue(str(generated.us_path).endswith("profiles/us/output/ipv4/result.m3u"))
        self.assertTrue(str(generated.cn_path).endswith("profiles/cn/output/ipv4/result.m3u"))

    def test_rejected_cn_output_does_not_block_accepted_us_or_replace_cn(self):
        seed_stable_playlists(self.root)
        generated = GeneratorRun(
            image_id="sha256:image123",
            repo_digests=("guovern/iptv-api@sha256:digest123",),
            us_path=write_output(self.root, "us", make_playlist(25)),
            cn_path=write_output(self.root, "cn", make_playlist(10)),
        )
        old_cn = (self.root / "vendor/live/auto-cn.m3u").read_bytes()
        results = publish_generated(self.root, generated)
        self.assertTrue(next(item for item in results if item.profile == "us").accepted)
        self.assertFalse(next(item for item in results if item.profile == "cn").accepted)
        self.assertEqual((self.root / "vendor/live/auto-cn.m3u").read_bytes(), old_cn)
        health = json.loads((self.root / "health/live-us.json").read_text(encoding="utf-8"))
        self.assertEqual(health["generator_image_id"], "sha256:image123")

    def test_commit_stages_only_four_generated_paths_and_never_force_pushes(self):
        runner = git_runner()
        self.assertTrue(commit_generated(self.root, runner=runner))
        commands = [call.args[0] for call in runner.call_args_list]
        add = next(command for command in commands if command[:2] == ["git", "add"])
        self.assertEqual(set(add[2:]), {
            "vendor/live/auto-us.m3u", "vendor/live/auto-cn.m3u",
            "health/live-us.json", "health/live-cn.json",
        })
        self.assertFalse(any("--force" in command for command in commands))
```

- [ ] **Step 2: Run the tests and confirm missing-module failure**

Run: `python -m unittest tests.test_nas -v`

Expected: FAIL because `hometv.nas` does not exist.

- [ ] **Step 3: Implement one pull, image inspection, and generator invocation**

Run these commands with `cwd=root`, `check=True`, captured text output, and no shell:

```python
compose = ["docker", "compose", "-f", "ops/iptv-api/compose.yaml"]
runner(compose + ["pull", "iptv-us"], cwd=root, check=True, text=True, capture_output=True)
inspection = runner(
    ["docker", "image", "inspect", "guovern/iptv-api:latest", "--format", '{{json .}}'],
    cwd=root, check=True, text=True, capture_output=True,
)
runner(compose + ["run", "--pull", "never", "--rm", "iptv-us"], cwd=root, check=True, text=True, capture_output=True)
runner(compose + ["run", "--pull", "never", "--rm", "iptv-cn"], cwd=root, check=True, text=True, capture_output=True)
```

Parse `inspection.stdout` as a JSON object, require non-empty `Id`, and normalize `RepoDigests` to a tuple of strings. Require both expected output files to exist, be non-empty, and have modification times after the run start. Raise `NasError` with operation/profile name and sanitized stderr on pull, inspection, or run failure. A failure before both profile runs leaves both stable playlists unchanged.

- [ ] **Step 4: Implement independent guarded publication**

Call `publish_playlist` separately for `us` and `cn`; one rejected profile does not undo an accepted sibling. Convert `PlaylistError` into `RunResult(accepted=False, channel_count=0, sha256="")` after `publish_playlist` writes rejected health metadata. After each result, atomically add `generator_image_id` and `generator_repo_digests` to that profile's health JSON. Return results in `us`, `cn` order.

- [ ] **Step 5: Implement exact Git scope and fast-forward-only behavior**

Before generation, require `git status --porcelain --untracked-files=no` to be empty. Before commit, run `git diff --name-only` and reject any changed tracked path outside the four-path allowlist. Stage the four exact paths, return `False` when `git diff --cached --quiet` succeeds, otherwise create the message with `f"Refresh regional live playlists {datetime.now(timezone.utc):%Y-%m-%d}"` and run `git push origin HEAD:main` without force flags. Do not invoke a Gitee remote in this function.

- [ ] **Step 6: Implement CLI behavior**

Both modes run generators and validate outputs. `--dry-run` validates bytes without calling `publish_playlist`, Git commit, or push, and prints reports. `--publish` publishes each profile independently and calls `commit_generated` whenever any of the four allowed playlist/health paths changed, including rejected health metadata. After archiving that metadata, return exit code 1 if both profiles are rejected or a Docker/Git safety check fails; return 0 when at least one profile is accepted.

- [ ] **Step 7: Run focused and full tests**

Run: `python -m unittest tests.test_nas -v`

Expected: PASS.

Run: `python -m unittest discover -s tests -v`

Expected: PASS, including the Phase 1 playlist guardrails.

- [ ] **Step 8: Commit**

```powershell
git add hometv/nas.py scripts/nas_refresh.py tests/test_nas.py
git commit -m "Add safe NAS playlist orchestration"
```

### Task 3: NAS Scheduler Entry Point and Operations Guide

**Files:**
- Create: `ops/iptv-api/run.sh`
- Create: `ops/iptv-api/README.md`
- Modify: `README.md`

**Interfaces:**
- Produces a non-interactive Synology Task Scheduler command.
- Documents dry-run, publish, rollback, logs, credentials, and `latest` image traceability.

- [ ] **Step 1: Add the scheduler shell entry point**

```sh
#!/bin/sh
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo_dir=$(CDPATH= cd -- "$script_dir/../.." && pwd)
lock_dir="$repo_dir/ops/iptv-api/.run-lock"

if ! mkdir "$lock_dir" 2>/dev/null; then
  echo "HomeTV IPTV refresh is already running" >&2
  exit 75
fi
trap 'rmdir "$lock_dir"' EXIT HUP INT TERM

cd "$repo_dir"
git fetch origin main
git merge --ff-only origin/main
python3 scripts/nas_refresh.py --publish
```

- [ ] **Step 2: Document initial dry-run commands**

```sh
cd /volume1/docker/hometv
docker compose -f ops/iptv-api/compose.yaml pull iptv-us
python3 scripts/nas_refresh.py --dry-run
python3 scripts/refresh.py verify --regions us cn --probe-origin us-nas
```

The guide requires manual review of both channel counts, the US rejection/acceptance ratio from generator logs, presence of CCTV/卫视 in CN, and sample N1 playback before using `--publish`.

- [ ] **Step 3: Document the 12-hour Synology schedule**

Use Control Panel → Task Scheduler → Create → Scheduled Task → User-defined script. Run as the dedicated repository owner, every 12 hours, with:

```sh
/bin/sh /volume1/docker/hometv/ops/iptv-api/run.sh >> /volume1/docker/hometv/ops/iptv-api/refresh.log 2>&1
```

Document Docker permission requirements, repository ownership, log rotation, and that the task must not run as `root` unless the NAS Docker installation requires it.

- [ ] **Step 4: Document credentials and Gitee boundary**

Use an existing repository-scoped GitHub SSH deploy key or fine-grained token stored in the NAS credential helper, never in the checkout. State that `run.sh` pushes only GitHub `origin`. Gitee remains a separate fast-forward sync step until the owner explicitly approves and installs a repository-scoped Gitee deploy key.

- [ ] **Step 5: Document playlist and image rollback**

When the most recent commit is the generated-playlist commit, playlist rollback is `git revert HEAD` followed by a normal push; permanent URLs never change. Every health file records the image ID and RepoDigest that produced its playlist. If a new `latest` image breaks generation, disable the scheduled task, inspect the last accepted health record, pull that recorded digest explicitly, tag it locally as `guovern/iptv-api:rollback`, change Compose to that tag in a reviewed emergency commit, and dry-run before re-enabling publication.

- [ ] **Step 6: Validate the shell script and documentation commands**

```powershell
docker compose -f ops/iptv-api/compose.yaml config
git diff --check
python -m unittest discover -s tests -v
```

Expected: Compose config renders, Git reports no whitespace errors, and all tests pass.

- [ ] **Step 7: Commit**

```powershell
git add ops/iptv-api/run.sh ops/iptv-api/README.md README.md
git commit -m "Document NAS live automation"
```

### Task 4: Dry Run, Controlled Activation, and Gitee Handoff

**Files:**
- Create: `docs/verification/2026-08-16-iptv-nas-dry-run.md`
- Generate after approval: `vendor/live/auto-us.m3u`
- Generate after approval: `vendor/live/auto-cn.m3u`
- Generate after approval: `health/live-us.json`
- Generate after approval: `health/live-cn.json`

**Interfaces:**
- Activates the NAS only after evidence review.

- [ ] **Step 1: Build and run without publication**

```sh
python3 scripts/nas_refresh.py --dry-run
```

Expected: both one-shot containers exit 0; both candidate outputs parse; dry-run does not modify `vendor/live/auto-*.m3u`, `health/live-*.json`, or Git history.

- [ ] **Step 2: Record evidence**

Record the resolved image ID and RepoDigest, NAS architecture, Docker version, start/end time, input subscription URLs, US/CN channel and URL counts, profiles' exact speed-test switches, playlist SHA-256 values, guardrail results, and ten sampled channels per profile. Explicitly state that US success does not prove mainland playback.

- [ ] **Step 3: Perform one controlled publication**

After reviewing the dry-run report:

```sh
python3 scripts/nas_refresh.py --publish
git log -1 --stat
```

Expected: only the four generated paths are committed; GitHub `main` receives a non-force push; rejected profile content remains on its prior version.

- [ ] **Step 4: Verify permanent delivery and N1 behavior**

Verify GitHub Raw US automatic playlist, Gitee Raw CN automatic playlist after fast-forward synchronization, both dedicated LiveConfig files, and representative N1 playback. Check that FongMi still uses the same Live URL and sees updated content without editing the box.

- [ ] **Step 5: Enable the 12-hour schedule**

Enable the Synology task only after the controlled publication and N1 check pass. Trigger it once manually, confirm the overlap lock, inspect `refresh.log`, and verify that an unchanged run creates no Git commit.

- [ ] **Step 6: Keep Gitee automation off until separately authorized**

Continue the existing reviewed fast-forward Gitee synchronization. When the owner explicitly authorizes persistent Gitee automation and provides a repository-scoped deploy key, add a separate `git push gitee HEAD:main` after the successful GitHub push, test with a no-change run, and document key rotation. Never add `--force`.

- [ ] **Step 7: Commit verification evidence**

```sh
git add docs/verification/2026-08-16-iptv-nas-dry-run.md
git commit -m "Record IPTV NAS dry run"
git push origin HEAD:main
```
