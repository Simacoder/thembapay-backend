"""
SUPERSEDED - kept only for reference, not imported anywhere.

This file has been replaced by app/integrations/eclipse_client.py, a
client shaped against Eclipse (EFT Corp)'s actual documented sandbox
endpoints - real endpoint paths, real JWT response shape, real payment
field names, all sourced from developer.eftcorp.com and verified with
tests against their documented sample responses.

Reasoning for the swap: Absa Access's developer portal
(developer.absa.africa) shows no self-serve registration flow, so
building against it would mean writing code against a guess rather than
a documented contract. Eclipse's sandbox is publicly documented, and
notably lists Absa Bank Limited as a supported bank (code 632005) - so
the demo can genuinely test payment rails involving Absa accounts today,
while Absa Access remains the named production integration target in the
pitch.

See app/integrations/eclipse_client.py for the current implementation.
"""
