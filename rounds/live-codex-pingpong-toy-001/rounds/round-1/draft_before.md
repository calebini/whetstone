# Toy Approval Adapter Spec

## Purpose

Define a tiny approval adapter contract for smoke testing Whetstone.

## Request

The adapter receives an approval request with `request_id`, `decision`, and `expires_at`.

## Response

The adapter returns `request_id`, `decision`, and `submitted_at`.

## Validation

The adapter should reject invalid decisions.
