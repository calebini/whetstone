"""Unit decisions on the active verified Phase 1 review, including vertical merges."""
from types import SimpleNamespace

from whetstone.vnext_contracts import decode_json, require
from whetstone.vnext_discovery import discovery_rules
from whetstone.vnext_inventory import seed_inventory
from whetstone.vnext_operator_decisions import _selection_ref, _validate_receipt
from whetstone.vnext_verified_phase2_binding import _ref
from whetstone.vnext_verified_phase2_operator import Phase2Operator
from whetstone.vnext_verified_review import VerifiedReview, _sequence
from whetstone.vnext_verified_review_requests import _ReviewInputs, _VerifiedReviewRequest


class Phase1Decisions(Phase2Operator):
    # Reuse the exact unit request/response protocol; only the review context and
    # its source barriers differ from Phase 2. No seed-only P owner is involved.
    _proof = VerifiedReview._proof
    _observe = VerifiedReview._observe

    def _context(self, proof):
        from whetstone.vnext_verified_vertical_phase1 import enabled, sequence
        frames, gate, _ = _sequence(proof)
        require(gate == 'finding_admission', 'operator work requires active completed findings')
        frame = frames[-1]
        values = proof.values(proof.latest)
        number = frame.request.number
        review = frame.review
        result = _ref(frame.request.directory+'/result.json', frame.receipt)
        vertical = sequence(proof) if enabled(proof.seed_values['review']) else None
        if vertical:
            packet, assets, _, present = vertical.merges[-1]
            require(present, 'operator work requires the committed vertical consolidation')
            number = vertical.number
            from whetstone.vnext_classification import classify_feedback
            feedback = decode_json(assets[packet['feedback']['path']])
            advice = decode_json(assets[packet['advice']['path']])
            findings, evidence = classify_feedback(feedback=feedback, feedback_ref=packet['feedback'],
                advice=advice, job=values['job'], authority=values['authority'], invariants=values['invariants'],
                base=values['base'], section_map=values['base_map'], scope=values['scope'])
            review = dict(findings=findings, evidence=evidence)
            result = _ref(f'rounds/round-{number}/vertical_merge.json', packet)
        inventory = values.get('base_inventory') or seed_inventory(values['base'], values['base_map'],
            values['job'], rules=discovery_rules(values['invariants']))
        step = SimpleNamespace(round_number=number, review=review)
        return dict(gate=gate), dict(owner=SimpleNamespace(number=number), source=frame,
                                    vertical=vertical), {}, (proof.reader, values, step, inventory, result)

    def _synchronize(self, store, proof, frame, binding):
        if frame['vertical']:
            from whetstone.vnext_verified_vertical_phase1 import publish_merge
            publish_merge(store, proof, frame['vertical'])
        else:
            source = frame['source']
            request = _VerifiedReviewRequest(_ReviewInputs(store, proof, proof.latest),
                                            source.request.number, source.request.profile)
            request.synchronize(store._token, source.header, source.outcomes)
            request.finish(store._token, source.review)

    def selected(self, reference):
        proof = self._proof(self.store.read)
        context = self._context(proof)[3]
        receipt = proof.reader.json(reference, 'vnext_operator_selection_v1')
        require(reference == _selection_ref(context[2].round_number, receipt), 'noncanonical operator selection')
        return _validate_receipt(self.run, receipt, context)
