FROM python:3.10.4-slim
LABEL author="akonrad - albert.konrad@edu.dsti.institute"
LABEL description="Streamlit Front-End for DSTI Coral Reef Project"
COPY . /streamlit
WORKDIR /streamlit
RUN python3 -m pip install -r requirements.txt
EXPOSE 8501
CMD streamlit run main.py