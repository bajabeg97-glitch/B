from pa800_optimizer.transaction_guard import audit_optimizer_transaction_bypasses

def test_optimizer_has_no_known_direct_mutation_bypasses():
    audit=audit_optimizer_transaction_bypasses()
    assert audit['pass'], audit['hits']
