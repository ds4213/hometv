# GitHub configuration verification — 2026-08-16

## Result

- `stable/us.json` and `stable/cn.json` are valid JSON objects and pass the repository's FongMi structural checks.
- The mainland configuration contains no `github.com` or `raw.githubusercontent.com` dependency.
- The mainland configuration is intentionally not usable from its final Gitee URL yet. Its four repository-owned static dependencies remain pending until the owner separately authorizes the Gitee synchronization.
- Local US-network probing passed every reachable dependency: US 15/15 and mainland external dependencies 11/11. Both reports retain a warning because the direct live-TV entry uses cleartext HTTP.
- Mainland multi-carrier checks confirm that the direct live-TV entry and the Wang Er Xiao candidate are broadly reachable. The Nitan Cloudflare endpoints are usable but materially less consistent across nodes.

## Mainland multi-carrier evidence

The tests used 17CE GET checks restricted to mainland China Telecom, China Unicom, and China Mobile nodes, with `User-Agent: okhttp/4.12.0` to approximate the FongMi Android network stack. A successful node returned HTTP 200 with non-empty content.

| Target | Role | HTTP 200 | Other result | Public evidence |
| --- | --- | ---: | ---: | --- |
| `https://nitan.ggff.net/config-dm.json` | Nitan upstream config | 79/170 | 82 download errors, 9 empty | [17CE result](https://www.17ce.com/site/http/20260817_4cd434c099b211f18349a743aebd33af:1.html) |
| `https://vod.catvod.ggff.net/guazi` | Representative Nitan video API | 68/170 | 93 download errors, 9 empty | [17CE result](https://www.17ce.com/site/http/20260817_69debef099b211f185556779fbda229b:1.html) |
| `https://9280.kstore.vip/aiwex.json` | Wang Er Xiao candidate | 162/170 | 8 empty | [17CE result](https://www.17ce.com/site/http/20260817_81ba3a9099b211f18349a743aebd33af:1.html) |
| `http://82.156.243.185:33389/fwc.m3u` | Direct live-TV entry | 160/170 | 10 empty | [17CE result](https://www.17ce.com/site/http/20260817_94bf27e099b211f185556779fbda229b:1.html) |

These are point-in-time reachability checks, not a guarantee that every channel or video remains playable. The upstream services can change without notice.

## Deliberate configuration changes

- The Nitan danmaku configuration is the only promoted stable source for both regions.
- GitHub-hosted Spider, database, Python, and IPTV files are mirrored into `vendor/` and rewritten to future Gitee Raw paths in `stable/cn.json`.
- Dead YanG lists were removed after both returned HTTP 404.
- The empty Migu list was removed because it contained only an `#EXTM3U` header and no playable channels.
- The Kimentanm list remains. Network verification skips dead leading entries and found a working CGTN stream.
- Wang Er Xiao remains an isolated candidate because its Spider bundle is independent and should not be merged blindly into the Nitan configuration.
- Aowu, Fantaiying, and OK remain disabled in `sources/registry.json` with dated reasons rather than silently disappearing.

## Gate completion

The GitHub change was merged, the owner authorized the Gitee synchronization, and the final Gitee configuration plus all mirrored static dependencies passed mainland multi-carrier checks. See `docs/verification/2026-08-16-gitee-verification.md` for the final evidence and permanent FongMi URL.
