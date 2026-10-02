.PHONY: deploy deploy-bootstrap check lint test deps clean

VAULT_TPL := group_vars/timeservers/vault.yml.tpl
VAULT_YML := group_vars/timeservers/vault.yml

# Normal idempotent re-run (admin SSH key must already be deployed)
deploy: _inject
	ansible-playbook playbook.yml
	@rm -f $(VAULT_YML)

# First-run: Pi Imager creates admin user with password auth
deploy-bootstrap: _inject
	ansible-playbook playbook.yml -u admin --ask-pass -e ssh_enforce_hardening=false --ssh-extra-args="-o IdentitiesOnly=yes"
	@rm -f $(VAULT_YML)

# Dry-run with diff (does not make changes)
check: _inject
	ansible-playbook playbook.yml --check --diff
	@rm -f $(VAULT_YML)

# Always re-inject from 1Password — never reuse a stale vault.yml
_inject:
	op inject -f -i $(VAULT_TPL) -o $(VAULT_YML)

deps:
	ansible-galaxy collection install -r requirements.yml

lint:
	ansible-lint playbook.yml

# Unit tests for the on-device Python tools (no hardware needed)
test:
	python3 -m unittest discover -s roles/gnsstool/tests

clean:
	rm -f $(VAULT_YML)
	rm -rf .ansible_cache
