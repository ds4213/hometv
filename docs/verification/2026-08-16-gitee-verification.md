# Gitee mainland verification — 2026-08-16

## Result

The GitHub `main` commit `2093e543df7b6da5fc6c4ac73bf83d16b7ffba51` was pushed to a new Gitee `main` branch without modifying the repository's pre-existing `master` branch. The permanent mainland FongMi URL is ready:

```text
https://gitee.com/ds4213tv/hometv/raw/main/stable/cn.json
```

All five repository-owned Gitee targets returned HTTP 200 from the local US validation host. The JSON parsed as a FongMi object with 14 sites and 2 live-TV entries.

## Mainland multi-carrier evidence

The final URLs were tested with 17CE GET checks restricted to mainland China Telecom, China Unicom, and China Mobile nodes, using `User-Agent: okhttp/4.12.0` to approximate FongMi's Android network stack.

| Target | HTTP 200 | Other result | Public evidence |
| --- | ---: | ---: | --- |
| `stable/cn.json` | 158/171 | 13 empty | [17CE result](https://www.17ce.com/site/http/20260817_a56cf3e099b411f18349a743aebd33af:1.html) |
| `vendor/nitan/awdm.png` | 162/171 | 9 empty | [17CE result](https://www.17ce.com/site/http/20260817_b73b35f099b411f185556779fbda229b:1.html) |
| `vendor/nitan/db.aowu` | 159/171 | 11 empty, 1 download error | [17CE result](https://www.17ce.com/site/http/20260817_cabb46b099b411f18349a743aebd33af:1.html) |
| `vendor/nitan/py/py_jinpai.py` | 158/171 | 12 empty, 1 download error | [17CE result](https://www.17ce.com/site/http/20260817_dc82aaf099b411f18349a743aebd33af:1.html) |
| `vendor/live/kimentanm.m3u` | 155/171 | 14 empty, 1 download error, 1 other | [17CE result](https://www.17ce.com/site/http/20260817_ee8172e099b411f185556779fbda229b:1.html) |

No test showed a broad HTTP 403 or HTTP 404 failure. These are point-in-time delivery checks; upstream channel and video availability can still change independently.

## Scope and remaining maintenance item

- The final Gitee configuration and every repository-owned dependency are reachable from all three mainland carriers.
- Nitan's dynamic video APIs and the direct live-TV entry were tested separately before synchronization; their results remain in the GitHub verification report.
- This was a manual, non-destructive push. Automatic GitHub-to-Gitee synchronization still requires a dedicated Gitee deploy credential stored as a GitHub Actions secret; no personal credential was copied or exposed during this setup.
