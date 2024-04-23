generate-readme:
	.venv/bin/python -c "from oncall_bot.mention_bot import MentionedBot; print('# Oncall Bot\n' + str(MentionedBot))" > README.md

docker-image:
	docker build -t oncall_bot -f docker/Dockerfile --platform linux/amd64 .

run:
	CONFIG_PATH=.env.yaml .venv/bin/python -m oncall_bot.main

create-secret-k8s:
	kubectl create secret generic -n $${NAMESPACE} slack-oncallbot-secrets --from-file=config.yaml=$${ENV_YAML} --dry-run=client  --output=yaml > "/tmp/secrets-$$(date +'%Y%m%d').yaml"
	@echo "/tmp/secrets-$$(date +'%Y%m%d').yaml"
