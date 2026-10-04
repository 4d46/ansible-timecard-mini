.PHONY: deploy deploy-bootstrap check lint test deps lock clean

VAULT_TPL := group_vars/timeservers/vault.yml.tpl
VAULT_YML := group_vars/timeservers/vault.yml

# Prefix for any recipe that runs with the decrypted vault on disk. Each recipe
# line is its own shell, so a separate 'rm' line never runs once the playbook
# fails. The trap removes the vault however the shell ends (success, failure
# or Ctrl-C) and leaves the playbook's exit code for make to see.
WITH_VAULT_CLEANUP := trap 'rm -f $(VAULT_YML)' EXIT INT TERM;

# Normal idempotent re-run (admin SSH key must already be deployed)
deploy: _inject
	$(WITH_VAULT_CLEANUP) ansible-playbook playbook.yml

# First-run: Pi Imager creates admin user with password auth
deploy-bootstrap: _inject
	$(WITH_VAULT_CLEANUP) ansible-playbook playbook.yml -u admin --ask-pass -e ssh_enforce_hardening=false --ssh-extra-args="-o IdentitiesOnly=yes"

# Dry-run with diff (does not make changes)
check: _inject
	$(WITH_VAULT_CLEANUP) ansible-playbook playbook.yml --check --diff

# Always re-inject from 1Password — never reuse a stale vault.yml
_inject:
	op inject -f -i $(VAULT_TPL) -o $(VAULT_YML)

# Python packages first: ansible-galaxy comes from them. --require-hashes makes
# pip refuse any file whose SHA-256 doesn't match the lock.
deps:
	pip install --require-hashes -r requirements.txt
	ansible-galaxy collection install -r requirements.yml

# Regenerate requirements.txt (the hash-pinned lock) from requirements.in,
# keeping the current versions. To upgrade one package on purpose:
#   make lock ARGS="--upgrade-package ansible"
# pip-tools runs in a throwaway environment via uvx, on the .tool-versions
# Python (UV_PYTHON_DOWNLOADS=never stops uv fetching its own); nothing is installed.
# click<8.3: pip-tools 7.6.1 with newer click writes a spurious --no-index into
# the lock's header, and Dependabot re-runs that command when it updates the lock.
lock:
	UV_PYTHON_DOWNLOADS=never uvx --python python3 --with 'click<8.3' --from pip-tools pip-compile \
		--generate-hashes --allow-unsafe --strip-extras --quiet \
		--output-file=requirements.txt requirements.in $(ARGS)

lint:
	ansible-lint playbook.yml

# Unit tests for the on-device Python tools (no hardware needed)
test:
	python3 -m unittest discover -s roles/gnsstool/tests

clean:
	rm -f $(VAULT_YML)
	rm -rf .ansible_cache
