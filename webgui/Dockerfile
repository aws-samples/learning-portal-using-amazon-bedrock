FROM public.ecr.aws/docker/library/python:3.9.18
EXPOSE 8501
WORKDIR /app
COPY requirements.txt ./requirements.txt
COPY Home.py ./Home.py
COPY components ./components
COPY pages ./pages
RUN pip3 install -r requirements.txt
RUN useradd -u 8877 demouser
RUN chown demouser .
RUN chmod -R 755 .
USER demouser
CMD streamlit run Home.py \
    --server.headless true \
    --browser.serverAddress="0.0.0.0" \
    --server.enableCORS false \
    --browser.gatherUsageStats false