# Suprema IG Scheduler

Posta automaticamente os stories recorrentes do **@asupremapizza** (cron na nuvem, sem app/celular).

## Como funciona
1. Mídias hospedadas em URL pública (Vercel, sem SSO) — `base_url` no `schedule.json`.
2. GitHub Actions roda `publish.py run` a cada 10 min na janela de postagem (cron UTC).
3. `publish.py` compara a hora atual (TZ America/Sao_Paulo) com `schedule.json`; se estiver na janela (±20min) e ainda não postou hoje, publica via Graph API (container → FINISHED → media_publish).
4. `posted-log.json` evita repostar o mesmo story no mesmo dia (idempotente).

## Suporta imagem E vídeo
Suprema posta 18h Horário (jpg) e 21h Feedback (jpg) além dos vídeos. O `publish.py` detecta pelo nome do arquivo: `.jpg/.png` → `image_url`, `.mp4` → `video_url`.

## Grade (24 stories/semana)
18h Horário · 19h Produto · 20h Remarketing · 21h Feedback (só Seg/Qua/Sex). Editar = editar `schedule.json`.

## Comandos
- `python3 publish.py next` — mostra a grade (não posta)
- `python3 publish.py dry` — mostra o que postaria agora (não posta)
- `python3 publish.py test <url>` — publica 1 story manual (validação)
- `python3 publish.py run` — publica os devidos na janela atual (usado pelo cron)

## Segredo
- `IG_TOKEN` (GitHub Secret) — Page Access Token permanente do @asupremapizza. Nunca commitado.
- `IG_ID` está no `schedule.json` (`17841447344788968`).

## Operação
- Pausar: `gh workflow disable "Suprema IG Stories" -R <repo>`
- Religar: `gh workflow enable "Suprema IG Stories" -R <repo>`
- Trocar token: `gh secret set IG_TOKEN -R <repo>` (via stdin)
