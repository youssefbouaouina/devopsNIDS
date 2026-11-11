# Gauntlt (Lab 3) with the attack adapters used by our .attack files (nmap, curl).
# Gauntlt 1.0.x relies on APIs removed in Ruby 3.2, so the image pins Ruby 3.1.
FROM ruby:3.1-slim-bookworm

RUN apt-get update \
 && apt-get install -y --no-install-recommends nmap curl build-essential \
 && gem install gauntlt --no-document \
 && apt-get purge -y build-essential && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /attacks
ENTRYPOINT ["gauntlt"]
