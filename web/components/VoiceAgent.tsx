"use client";

import { useCallback, useState, useRef, useEffect } from "react";
import {
  LiveKitRoom,
  useVoiceAssistant,
  BarVisualizer,
  RoomAudioRenderer,
  DisconnectButton,
} from "@livekit/components-react";

type ConnectionState = "disconnected" | "connecting" | "connected";

interface TranscriptEntry {
  id: string;
  role: "user" | "assistant";
  text: string;
  isFinal: boolean;
}

function VoiceUI() {
  const { state, audioTrack, agentTranscriptions } = useVoiceAssistant();
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);
  const transcriptEndRef = useRef<HTMLDivElement>(null);

  // Track agent transcriptions
  useEffect(() => {
    if (!agentTranscriptions || agentTranscriptions.length === 0) return;

    setTranscript((prev) => {
      const updated = [...prev];
      for (const seg of agentTranscriptions) {
        const id = `agent-${seg.id}`;
        const existing = updated.findIndex((e) => e.id === id);
        if (existing >= 0) {
          updated[existing] = {
            ...updated[existing],
            text: seg.text,
            isFinal: seg.final,
          };
        } else {
          updated.push({
            id,
            role: "assistant",
            text: seg.text,
            isFinal: seg.final,
          });
        }
      }
      return updated;
    });
  }, [agentTranscriptions]);

  // Auto-scroll
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript]);

  const stateLabel: Record<string, string> = {
    disconnected: "გათიშულია",
    idle: "მზადაა — ილაპარაკეთ",
    listening: "ვუსმენ...",
    thinking: "ვფიქრობ...",
    speaking: "ვპასუხობ...",
  };

  const stateColors: Record<string, string> = {
    disconnected: "#666",
    idle: "#3b82f6",
    listening: "#22c55e",
    thinking: "#eab308",
    speaking: "#8b5cf6",
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: "1.5rem",
        padding: "2rem 1rem",
        maxWidth: "600px",
        margin: "0 auto",
        minHeight: "100dvh",
      }}
    >
      <style>{`
        @keyframes pulse-ring {
          0% { transform: scale(1); opacity: 0.5; }
          100% { transform: scale(1.6); opacity: 0; }
        }
        @keyframes pulse-dot {
          0%, 100% { transform: scale(1); }
          50% { transform: scale(1.05); }
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        .status-dot {
          display: inline-block;
          width: 10px;
          height: 10px;
          border-radius: 50%;
          margin-right: 8px;
          transition: background-color 0.3s;
        }
        .status-dot.listening {
          animation: pulse-dot 1s ease-in-out infinite;
        }
      `}</style>

      {/* Header */}
      <h1 style={{ fontSize: "1.3rem", fontWeight: 600, margin: 0 }}>
        🇬🇪 Georgian Voice AI
      </h1>

      {/* Status */}
      <div
        style={{
          fontSize: "1rem",
          color: stateColors[state] || "#666",
          fontWeight: 500,
          display: "flex",
          alignItems: "center",
          transition: "color 0.3s",
        }}
      >
        <span
          className={`status-dot ${state === "listening" ? "listening" : ""}`}
          style={{ backgroundColor: stateColors[state] || "#666" }}
        />
        {stateLabel[state] || state}
      </div>

      {/* Visualizer */}
      <div
        style={{
          width: "100%",
          height: "100px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          position: "relative",
        }}
      >
        {audioTrack ? (
          <BarVisualizer
            state={state}
            trackRef={audioTrack}
            barCount={24}
            style={{ width: "100%", height: "100%" }}
          />
        ) : (
          <div
            style={{
              width: "100px",
              height: "100px",
              borderRadius: "50%",
              border: `3px solid ${stateColors[state] || "#333"}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "border-color 0.3s",
              position: "relative",
            }}
          >
            {state === "listening" && (
              <>
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    borderRadius: "50%",
                    border: `2px solid ${stateColors.listening}`,
                    animation: "pulse-ring 1.5s ease-out infinite",
                  }}
                />
                <div
                  style={{
                    position: "absolute",
                    inset: 0,
                    borderRadius: "50%",
                    border: `2px solid ${stateColors.listening}`,
                    animation: "pulse-ring 1.5s ease-out infinite 0.5s",
                  }}
                />
              </>
            )}
            <svg
              width="40"
              height="40"
              viewBox="0 0 24 24"
              fill="none"
              stroke={stateColors[state] || "#666"}
              strokeWidth="2"
            >
              <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1="12" y1="19" x2="12" y2="23" />
              <line x1="8" y1="23" x2="16" y2="23" />
            </svg>
          </div>
        )}
      </div>

      {/* Disconnect */}
      <DisconnectButton
        style={{
          padding: "0.6rem 1.5rem",
          borderRadius: "8px",
          border: "1px solid #333",
          backgroundColor: "#1a1a1a",
          color: "#ededed",
          cursor: "pointer",
          fontSize: "0.85rem",
        }}
      >
        გათიშვა
      </DisconnectButton>

      {/* Chat Transcript */}
      <div
        style={{
          width: "100%",
          flex: 1,
          borderTop: "1px solid #222",
          paddingTop: "1rem",
          maxHeight: "40vh",
          overflowY: "auto",
        }}
      >
        {transcript.length === 0 && (
          <p
            style={{
              textAlign: "center",
              color: "#555",
              fontSize: "0.85rem",
              fontStyle: "italic",
            }}
          >
            საუბარი აქ გამოჩნდება...
          </p>
        )}
        {transcript.map((entry) => (
          <div
            key={entry.id}
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: entry.role === "user" ? "flex-end" : "flex-start",
              marginBottom: "0.75rem",
              opacity: entry.isFinal ? 1 : 0.6,
              transition: "opacity 0.3s",
            }}
          >
            <span
              style={{
                fontSize: "0.7rem",
                color: "#555",
                marginBottom: "0.2rem",
              }}
            >
              {entry.role === "user" ? "თქვენ" : "AI"}
            </span>
            <div
              style={{
                padding: "0.6rem 1rem",
                borderRadius: "1rem",
                maxWidth: "85%",
                fontSize: "0.9rem",
                lineHeight: 1.5,
                backgroundColor:
                  entry.role === "user" ? "#1a3a5c" : "#2a1a3e",
                color: "#ededed",
              }}
            >
              {entry.text}
            </div>
          </div>
        ))}
        <div ref={transcriptEndRef} />
      </div>

      <RoomAudioRenderer />
    </div>
  );
}

export default function VoiceAgent() {
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("disconnected");
  const [token, setToken] = useState<string>("");
  const [url, setUrl] = useState<string>("");
  const [error, setError] = useState<string>("");

  const connect = useCallback(async () => {
    setConnectionState("connecting");
    setError("");

    try {
      const resp = await fetch("/api/token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ room: `voice-ai-${Date.now()}` }),
      });

      if (!resp.ok) throw new Error(`Token request failed: ${resp.status}`);

      const data = await resp.json();
      setToken(data.token);
      setUrl(data.url);
      setConnectionState("connected");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Connection failed");
      setConnectionState("disconnected");
    }
  }, []);

  if (connectionState === "disconnected") {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "100dvh",
          gap: "2rem",
        }}
      >
        <h1 style={{ fontSize: "2rem", fontWeight: 600 }}>
          🇬🇪 Georgian Voice AI
        </h1>
        <p style={{ color: "#888", maxWidth: "400px", textAlign: "center" }}>
          ილაპარაკეთ ქართულად ხელოვნურ ინტელექტთან
        </p>

        <button
          onClick={connect}
          style={{
            width: "160px",
            height: "160px",
            borderRadius: "50%",
            border: "3px solid #3b82f6",
            backgroundColor: "transparent",
            color: "#3b82f6",
            cursor: "pointer",
            fontSize: "1rem",
            fontWeight: 500,
            transition: "all 0.2s",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexDirection: "column",
            gap: "0.5rem",
            WebkitTapHighlightColor: "transparent",
          }}
        >
          <svg
            width="48"
            height="48"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" y1="19" x2="12" y2="23" />
            <line x1="8" y1="23" x2="16" y2="23" />
          </svg>
          დაწყება
        </button>

        {error && (
          <p style={{ color: "#ef4444", fontSize: "0.9rem" }}>{error}</p>
        )}
      </div>
    );
  }

  if (connectionState === "connecting") {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "100dvh",
          color: "#888",
          gap: "1rem",
        }}
      >
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        <div
          style={{
            width: "40px",
            height: "40px",
            border: "3px solid #333",
            borderTopColor: "#3b82f6",
            borderRadius: "50%",
            animation: "spin 1s linear infinite",
          }}
        />
        იტვირთება...
      </div>
    );
  }

  return (
    <LiveKitRoom
      serverUrl={url}
      token={token}
      connect={true}
      audio={true}
      onDisconnected={() => setConnectionState("disconnected")}
      style={{ minHeight: "100dvh" }}
    >
      <VoiceUI />
    </LiveKitRoom>
  );
}
