# Shuv

Shuv's site, docs and pricing live at **https://shuv.cloud**. The GitHub Pages site here (https://13bfc3s.github.io/shuv/) only forwards there, so there is one copy of the prices and product details.

## GitHub Action: approve from your phone

Holds a job until someone answers on their phone. The step passes only if the answer is one of `pass-on` (default: the first option).

```yaml
- uses: 13bfc3s/shuv@v1
  with:
    key: ${{ secrets.SHUV_KEY }}
    question: Deploy ${{ github.sha }} to production?
    timeout: 30m
    default: Reject        # nobody answers -> the step fails safely
- run: ./deploy.sh
```

Inputs: `key` (required, from a secret), `question` (required), `details`, `options` (default `Approve,Reject`), `pass-on`, `timeout` (default `30m`), `default`, `team` (ask everyone on your Shuv team), `escalate` (e.g. `5m`: ask the rest of the team if you haven't answered), `api`.
Outputs: `answer`, `answered-by`, `timed-out`.

Get an API key at https://shuv.cloud. Full docs: https://shuv.cloud/docs#integrations
