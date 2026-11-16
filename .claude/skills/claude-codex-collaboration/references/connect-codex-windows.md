# Connect Codex to Claude Code on Windows (ChatGPT sign-in, no API key)

Checked against OpenAI's Codex docs on 2026-11-16. Each step says how to tell it worked. Stop at the first step that does not.

1. Open a new PowerShell window. Run `claude --version` and `git --version`. Both must print a version. If `claude` is missing, install Claude Code from Anthropic's docs first.
2. Install the Codex CLI with OpenAI's Windows installer, from a new PowerShell window:
   `powershell -ExecutionPolicy ByPass -c "irm https://chatgpt.com/codex/install.ps1 | iex"`
   (npm alternative: `npm install -g @openai/codex`). Close PowerShell, open a new one, run `codex --version`.
3. Sign in: `codex login`. A browser opens; choose Sign in with ChatGPT and use your ChatGPT account. Do not choose the API key option and do not set `OPENAI_API_KEY`; API keys bill per use. Check with `codex login status`.
4. Check that your ChatGPT plan includes Codex (on its settings or usage page). Codex use counts against that plan, not against Claude.
5. Get the setup branch: in each repo folder, `git fetch origin` then `git switch ai-dev-system`.
6. Check that Codex sees the shared rules and skills: in the scrubber folder run `codex`, type `/skills`, and confirm scrubber-qa, project-handoff, code-exploration, claude-codex-collaboration and learning-mode are listed. Then ask: "In one sentence, what does AGENTS.md say about patient data?" Exit Codex.
7. Register Codex as an MCP server for Claude Code, at user scope so nothing is written into the repos:
   `claude mcp add codex --scope user -- codex mcp-server`
   Check with `claude mcp list` (codex should show connected), or `/mcp` inside Claude Code.
   Use only the built-in `codex mcp-server` command. Do not use `npx -y codex` or third-party "codex-mcp-server" packages; they are not OpenAI's.
8. In Claude Code, run `/plugin` and confirm codex-dispatch is installed. If it is not: `/plugin install codex-dispatch@claude-plugins-official`.
9. First real exchange, read-only: open Claude Code in the scrubber folder and say "Get Codex to review the request in HANDOFF.md." Claude passes the diff command with `sandbox: read-only`; Codex's findings come back into Claude's session and go into the REVIEW block.

If Codex or Claude asks to run with full access, without a sandbox, or with approvals bypassed, say no. That is never needed for a review.
