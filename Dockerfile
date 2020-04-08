# use Debian python instance, not alpine
# https://pythonspeed.com/articles/alpine-docker-python/
FROM python:3.8-slim

# Install voila and dependencies needed for portfolio project
RUN pip install pandas matplotlib voila ipywidgets smartsheet-python-sdk XlsxWriter

# Copy voila template into image
COPY portfolio-voila-template /usr/local/share/jupyter/voila/templates/portfolio

# expose voila port
EXPOSE 8866

# start voila process
CMD voila \
    --no-browser \
    --VoilaConfiguration.file_whitelist="['.ico', '.*\.(xlsx)']" \
    --template=portfolio \
    /tmp/nz_portfolio_dashboard.ipynb

