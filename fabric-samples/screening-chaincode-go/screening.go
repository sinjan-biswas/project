package main

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

const (
	privCollection = "screeningPrivateDetails"
)

type ScreeningContract struct {
	contractapi.Contract
}

type Screening struct {
	ScreeningID    string  `json:"screening_id"`
	DocumentHash   string  `json:"document_hash"`
	PassportHash   string  `json:"passport_hash"`
	RiskScore      float64 `json:"risk_score"`
	Decision       string  `json:"decision"`
	CheckpointID   string  `json:"checkpoint_id"`
	Timestamp      string  `json:"timestamp"`
	AgentSignature string  `json:"agent_signature"`
}

type ScreeningPII struct {
	ScreeningID    string `json:"screening_id"`
	Name           string `json:"name"`
	FatherName     string `json:"father_name"`
	PassportNumber string `json:"passport_number"`
	DateOfBirth    string `json:"date_of_birth"`
}

type FraudAlert struct {
	AlertID      string `json:"alert_id"`
	AlertType    string `json:"alert_type"`
	ScreeningID  string `json:"screening_id"`
	PassportHash string `json:"passport_hash"`
	Severity     string `json:"severity"`
	Description  string `json:"description"`
	CreatedAt    string `json:"created_at"`
}

// txTime returns the deterministic transaction timestamp (same across all endorsers).
func txTime(ctx contractapi.TransactionContextInterface) time.Time {
	ts, err := ctx.GetStub().GetTxTimestamp()
	if err != nil || ts == nil {
		return time.Unix(0, 0).UTC()
	}
	return time.Unix(ts.Seconds, int64(ts.Nanos)).UTC()
}

// ---------------------------------------------------------------------------
// Public + private writes
// ---------------------------------------------------------------------------

func (s *ScreeningContract) RecordScreening(
	ctx contractapi.TransactionContextInterface,
	screeningJSON string,
	piiJSON string,
) error {
	var sc Screening
	if err := json.Unmarshal([]byte(screeningJSON), &sc); err != nil {
		return fmt.Errorf("invalid screening json: %w", err)
	}
	if sc.ScreeningID == "" || sc.PassportHash == "" {
		return fmt.Errorf("screening_id and passport_hash required")
	}

	bytes, _ := json.Marshal(sc)
	if err := ctx.GetStub().PutState("screening:"+sc.ScreeningID, bytes); err != nil {
		return err
	}

	idx1, _ := ctx.GetStub().CreateCompositeKey("passport~screening",
		[]string{sc.PassportHash, sc.ScreeningID})
	ctx.GetStub().PutState(idx1, bytes)

	idx2, _ := ctx.GetStub().CreateCompositeKey("checkpoint~screening",
		[]string{sc.CheckpointID, sc.ScreeningID})
	ctx.GetStub().PutState(idx2, bytes)

	if piiJSON != "" {
		if err := ctx.GetStub().PutPrivateData(privCollection, sc.ScreeningID, []byte(piiJSON)); err != nil {
			return fmt.Errorf("private data write failed: %w", err)
		}
	}

	if alerts, err := s.runFraudChecks(ctx, sc); err == nil {
		for _, a := range alerts {
			if err := s.writeAlert(ctx, a); err != nil {
				fmt.Printf("alert write failed: %v\n", err)
			}
		}
	}

	ctx.GetStub().SetEvent("ScreeningRecorded", bytes)
	return nil
}

func (s *ScreeningContract) GetScreening(
	ctx contractapi.TransactionContextInterface,
	screeningID string,
) (*Screening, error) {
	bytes, err := ctx.GetStub().GetState("screening:" + screeningID)
	if err != nil || bytes == nil {
		return nil, fmt.Errorf("screening %s not found", screeningID)
	}
	var sc Screening
	json.Unmarshal(bytes, &sc)
	return &sc, nil
}

func (s *ScreeningContract) GetScreeningPII(
	ctx contractapi.TransactionContextInterface,
	screeningID string,
) (string, error) {
	bytes, err := ctx.GetStub().GetPrivateData(privCollection, screeningID)
	if err != nil {
		return "", err
	}
	if bytes == nil {
		return "", fmt.Errorf("private data for %s not found", screeningID)
	}
	return string(bytes), nil
}

// ---------------------------------------------------------------------------
// Rich queries — the `_id` regex excludes composite-key indices and alerts
// ---------------------------------------------------------------------------

func (s *ScreeningContract) QueryScreeningsByPassport(
	ctx contractapi.TransactionContextInterface,
	passportHash string,
) ([]*Screening, error) {
	q := fmt.Sprintf(
		`{"selector":{"passport_hash":"%s","_id":{"$regex":"^screening:"}},"sort":[{"timestamp":"desc"}]}`,
		passportHash,
	)
	return s.queryScreenings(ctx, q)
}

func (s *ScreeningContract) QueryScreeningsByCheckpoint(
	ctx contractapi.TransactionContextInterface,
	checkpointID string,
) ([]*Screening, error) {
	q := fmt.Sprintf(
		`{"selector":{"checkpoint_id":"%s","_id":{"$regex":"^screening:"}}}`,
		checkpointID,
	)
	return s.queryScreenings(ctx, q)
}

func (s *ScreeningContract) CheckIdentityReuse(
	ctx contractapi.TransactionContextInterface,
	passportHash string,
	windowDays int,
) ([]*Screening, error) {
	cutoff := txTime(ctx).AddDate(0, 0, -windowDays).Format(time.RFC3339)
	q := fmt.Sprintf(
		`{"selector":{"passport_hash":"%s","timestamp":{"$gt":"%s"},"_id":{"$regex":"^screening:"}}}`,
		passportHash, cutoff,
	)
	return s.queryScreenings(ctx, q)
}

func (s *ScreeningContract) CheckImpossibleTravel(
	ctx contractapi.TransactionContextInterface,
	passportHash string,
	currentCheckpoint string,
	hoursWindow int,
) (*FraudAlert, error) {
	cutoff := txTime(ctx).Add(-time.Duration(hoursWindow) * time.Hour).Format(time.RFC3339)
	q := fmt.Sprintf(
		`{"selector":{"passport_hash":"%s","timestamp":{"$gt":"%s"},"_id":{"$regex":"^screening:"}},"sort":[{"timestamp":"desc"}],"limit":1}`,
		passportHash, cutoff,
	)
	results, err := s.queryScreenings(ctx, q)
	if err != nil || len(results) == 0 {
		return nil, nil
	}
	last := results[0]
	if last.CheckpointID == currentCheckpoint {
		return nil, nil
	}
	distance := checkpointDistance(last.CheckpointID, currentCheckpoint)
	kmh := distance / float64(hoursWindow)
	if kmh < 900 {
		return nil, nil
	}
	return &FraudAlert{
		AlertID:      fmt.Sprintf("alert_%s_travel", last.ScreeningID),
		AlertType:    "IMPOSSIBLE_TRAVEL",
		ScreeningID:  last.ScreeningID,
		PassportHash: passportHash,
		Severity:     "CRITICAL",
		Description: fmt.Sprintf("Traveled %.0f km from %s to %s within %dh (%.0f km/h)",
			distance, last.CheckpointID, currentCheckpoint, hoursWindow, kmh),
		CreatedAt: txTime(ctx).Format(time.RFC3339),
	}, nil
}

// ---------------------------------------------------------------------------
// Alerts
// ---------------------------------------------------------------------------

func (s *ScreeningContract) GetAlert(
	ctx contractapi.TransactionContextInterface,
	alertID string,
) (*FraudAlert, error) {
	bytes, err := ctx.GetStub().GetState("alert:" + alertID)
	if err != nil || bytes == nil {
		return nil, fmt.Errorf("alert %s not found", alertID)
	}
	var a FraudAlert
	json.Unmarshal(bytes, &a)
	return &a, nil
}

func (s *ScreeningContract) GetAlertsByPassport(
	ctx contractapi.TransactionContextInterface,
	passportHash string,
) ([]*FraudAlert, error) {
	q := fmt.Sprintf(
		`{"selector":{"passport_hash":"%s","_id":{"$regex":"^alert:"}}}`,
		passportHash,
	)
	return s.queryAlerts(ctx, q)
}

func (s *ScreeningContract) writeAlert(ctx contractapi.TransactionContextInterface, a FraudAlert) error {
	bytes, _ := json.Marshal(a)
	if err := ctx.GetStub().PutState("alert:"+a.AlertID, bytes); err != nil {
		return err
	}
	idx, _ := ctx.GetStub().CreateCompositeKey("passport~alert",
		[]string{a.PassportHash, a.AlertID})
	return ctx.GetStub().PutState(idx, bytes)
}

func (s *ScreeningContract) runFraudChecks(
	ctx contractapi.TransactionContextInterface,
	sc Screening,
) ([]FraudAlert, error) {
	var alerts []FraudAlert

	recent, err := s.CheckIdentityReuse(ctx, sc.PassportHash, 7)
	if err == nil && len(recent) >= 2 {
		alerts = append(alerts, FraudAlert{
			AlertID:      fmt.Sprintf("alert_%s_ir", sc.ScreeningID),
			AlertType:    "IDENTITY_REUSE",
			ScreeningID:  sc.ScreeningID,
			PassportHash: sc.PassportHash,
			Severity:     "HIGH",
			Description:  fmt.Sprintf("Passport used %d times in 7 days", len(recent)+1),
			CreatedAt:    txTime(ctx).Format(time.RFC3339),
		})
	}

	if ta, _ := s.CheckImpossibleTravel(ctx, sc.PassportHash, sc.CheckpointID, 24); ta != nil {
		ta.ScreeningID = sc.ScreeningID
		alerts = append(alerts, *ta)
	}

	return alerts, nil
}

// ---------------------------------------------------------------------------
// Internal query helpers
// ---------------------------------------------------------------------------

func (s *ScreeningContract) queryScreenings(
	ctx contractapi.TransactionContextInterface,
	query string,
) ([]*Screening, error) {
	iter, err := ctx.GetStub().GetQueryResult(query)
	if err != nil {
		return nil, err
	}
	defer iter.Close()
	var out []*Screening
	for iter.HasNext() {
		qr, err := iter.Next()
		if err != nil {
			return nil, err
		}
		var sc Screening
		json.Unmarshal(qr.Value, &sc)
		out = append(out, &sc)
	}
	return out, nil
}

func (s *ScreeningContract) queryAlerts(
	ctx contractapi.TransactionContextInterface,
	query string,
) ([]*FraudAlert, error) {
	iter, err := ctx.GetStub().GetQueryResult(query)
	if err != nil {
		return nil, err
	}
	defer iter.Close()
	var out []*FraudAlert
	for iter.HasNext() {
		qr, err := iter.Next()
		if err != nil {
			return nil, err
		}
		var a FraudAlert
		json.Unmarshal(qr.Value, &a)
		out = append(out, &a)
	}
	return out, nil
}

// ---------------------------------------------------------------------------
// Checkpoint distance table
// ---------------------------------------------------------------------------

func checkpointDistance(a, b string) float64 {
	dists := map[string]map[string]float64{
		"JFK_01": {"LHR_01": 5540, "CDG_01": 5840, "DXB_01": 11000, "BOM_01": 12550},
		"LHR_01": {"JFK_01": 5540, "CDG_01": 350, "DXB_01": 5500, "BOM_01": 7200},
		"CDG_01": {"JFK_01": 5840, "LHR_01": 350, "DXB_01": 5250, "BOM_01": 7000},
		"DXB_01": {"JFK_01": 11000, "LHR_01": 5500, "CDG_01": 5250, "BOM_01": 1930},
		"BOM_01": {"JFK_01": 12550, "LHR_01": 7200, "CDG_01": 7000, "DXB_01": 1930},
	}
	if m, ok := dists[a]; ok {
		if d, ok := m[b]; ok {
			return d
		}
	}
	return 1000
}

func main() {
	cc, err := contractapi.NewChaincode(&ScreeningContract{})
	if err != nil {
		panic(err)
	}
	if err := cc.Start(); err != nil {
		panic(err)
	}
}