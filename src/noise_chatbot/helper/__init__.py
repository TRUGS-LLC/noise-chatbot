"""noise-helper — stdin/stdout Noise_IK bridge binary.

<trl>
DEFINE "helper" AS PROCESS.
PROCESS helper READS RECORD Message FROM ENTRY stdin THEN SEND TO ENDPOINT server.
PROCESS helper READS RECORD Message FROM ENDPOINT server THEN WRITE TO EXIT stdout.
EACH RECORD Message SHALL AUTHENTICATE BY RECORD noise_ik.
</trl>
"""
