
Set-Location "C:\Users\ana\OneDrive\Desktop\BOT takip 20"
$prompt = Get-Content -Path "C:\Users\ana\OneDrive\Desktop\BOT takip 20\_ai_prompt_tmp.txt" -Raw -Encoding UTF8
claude --dangerously-skip-permissions -p $prompt
