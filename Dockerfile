FROM python:3

WORKDIR /usr/src/app

COPY REQUIREMENTS .
RUN pip install -r REQUIREMENTS

COPY entrypoint.sh .
COPY tesla-history.py .

ENTRYPOINT [ "/bin/bash" ]

CMD [ "/usr/src/app/entrypoint.sh" ]
