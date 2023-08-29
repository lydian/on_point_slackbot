generate-readme:
	.venv/bin/python -c "from oncall_bot.bot import MentionedBot; print('# Oncall Bot\n' + str(MentionedBot))" > README.md

docker:
	docker build -t oncall_bot -f docker/Dockerfile --platform linux/amd64 .
