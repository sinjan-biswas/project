import json
import os
import subprocess
from pathlib import Path

BASE = Path.home() / "Documents/project/fabric-samples/test-network"


class FabricClient:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _env(self):
        e = os.environ.copy()
        e["FABRIC_CFG_PATH"] = str(BASE.parent / "config")
        e["CORE_PEER_TLS_ENABLED"] = "true"
        e["CORE_PEER_LOCALMSPID"] = "Org1MSP"
        e["CORE_PEER_TLS_ROOTCERT_FILE"] = str(
            BASE / "organizations/peerOrganizations/org1.example.com/tlsca/tlsca.org1.example.com-cert.pem"
        )
        e["CORE_PEER_MSPCONFIGPATH"] = str(
            BASE / "organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp"
        )
        e["CORE_PEER_ADDRESS"] = "localhost:7051"
        return e

    def _org1_tls(self):
        return str(BASE / "organizations/peerOrganizations/org1.example.com/tlsca/tlsca.org1.example.com-cert.pem")

    def _org2_tls(self):
        return str(BASE / "organizations/peerOrganizations/org2.example.com/tlsca/tlsca.org2.example.com-cert.pem")

    def _orderer_ca(self):
        return str(BASE / "organizations/ordererOrganizations/example.com/tlsca/tlsca.example.com-cert.pem")

    def record_screening(self, screening: dict, pii: dict | None = None, channel: str = "screening-channel") -> str:
        args = json.dumps({
            "Args": [
                "RecordScreening",
                json.dumps(screening),
                json.dumps(pii) if pii else "",
            ]
        })
        result = subprocess.run(
            [
                "peer", "chaincode", "invoke",
                "-o", "localhost:7050",
                "--ordererTLSHostnameOverride", "orderer.example.com",
                "--tls", "--cafile", self._orderer_ca(),
                "-C", channel,
                "-n", "screening",
                "--peerAddresses", "localhost:7051",
                "--tlsRootCertFiles", self._org1_tls(),
                "--peerAddresses", "localhost:9051",
                "--tlsRootCertFiles", self._org2_tls(),
                "-c", args,
            ],
            env=self._env(), check=True, capture_output=True, text=True,
        )
        return result.stdout.strip()

    def get_screening(self, screening_id: str, channel: str = "screening-channel") -> dict:
        args = json.dumps({"Args": ["GetScreening", screening_id]})
        result = subprocess.run(
            ["peer", "chaincode", "query", "-C", channel, "-n", "screening", "-c", args],
            env=self._env(), check=True, capture_output=True, text=True,
        )
        return json.loads(result.stdout.strip())

    def get_screening_pii(self, screening_id: str) -> dict:
        args = json.dumps({"Args": ["GetScreeningPII", screening_id]})
        result = subprocess.run(
            ["peer", "chaincode", "query", "-C", "screening-channel", "-n", "screening", "-c", args],
            env=self._env(), check=True, capture_output=True, text=True,
        )
        return json.loads(result.stdout.strip())

    def query_by_passport(self, passport_hash: str) -> list:
        args = json.dumps({"Args": ["QueryScreeningsByPassport", passport_hash]})
        result = subprocess.run(
            ["peer", "chaincode", "query", "-C", "screening-channel", "-n", "screening", "-c", args],
            env=self._env(), check=True, capture_output=True, text=True,
        )
        return json.loads(result.stdout.strip())

    def get_alerts_by_passport(self, passport_hash: str) -> list:
        args = json.dumps({"Args": ["GetAlertsByPassport", passport_hash]})
        result = subprocess.run(
            ["peer", "chaincode", "query", "-C", "screening-channel", "-n", "screening", "-c", args],
            env=self._env(), check=True, capture_output=True, text=True,
        )
        return json.loads(result.stdout.strip())

    def broadcast_alert(self, screening: dict) -> str:
        """Mirror a high-risk screening to the cross-border global channel."""
        return self.record_screening(
            screening=screening,
            pii=None,
            channel="screening-channel-global",
        )