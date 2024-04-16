FROM python:3.11

COPY tox.ini requirements-dev.txt  /
RUN python -m pip install tox

RUN tox -e venv
COPY ./oncall_bot /oncall_bot

ENTRYPOINT [ ".venv/bin/python", "-u", "-m", "oncall_bot.main"]

USER nobody
