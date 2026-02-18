"use client";

import { useCallback, useState } from "react";
import {
  LiveKitRoom,
  useVoiceAssistant,
  BarVisualizer,
  RoomAudioRenderer,
  DisconnectButton,
} from "@livekit/components-react";

type ConnectionState = "disconnected" | "connecting" | "connected";

interface TranscriptEntry {
  role: "user" | "assistant";
  text: string;
  timestamp: Date;
}

function VoiceUI() {
  const { state, audioTrack } = useVoiceAssistant();
  const [transcript, setTranscript] = useState<TranscriptEntry[]>([]);

  const stateLabel: Record<string, string> = {
    disconnected: "გათიშულია",
    idle: "მზადაა",
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
        gap: "2rem",
        padding: "2rem",
        maxWidth: "600px",
        margin: "0 auto",
      }}
    >
      {/* Status indicator */}
      <div
        style={{
          fontSize: "1.1rem",
          color: stateColors[state] || "#666",
          fontWeight: 500,
          minHeight: "1.5em",
        }}
      >
        {stateLabel[state] || state}
      </div>

      {/* Audio visualizer */}
      <div
        style={{
          width: "100%",
          height: "120px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
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
              width: "120px",
              height: "120px",
              borderRadius: "50%",
              border: `3px solid ${stateColors[state] || "#333"}`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "border-color 0.3s",
            }}
          >
            <svg
              width="48"
              height="48"
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

      {/* Disconnect button */}
      <DisconnectButton
        style={{
          padding: "0.75rem 2rem",
          borderRadius: "8px",
          border: "1px solid #333",
          backgroundColor: "#1a1a1a",
          color: "#ededed",
          cursor: "pointer",
          fontSize: "0.9rem",
        }}
      >
        გათიშვა
      </DisconnectButton>

      {/* Audio renderer (plays agent audio) */}
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

      if (!resp.ok) {
        throw new Error(`Token request failed: ${resp.status}`);
      }

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
          minHeight: "100vh",
          gap: "2rem",
        }}
      >
        <h1 style={{ fontSize: "2rem", fontWeight: 600 }}>
          Georgian Voice AI
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
          alignItems: "center",
          justifyContent: "center",
          minHeight: "100vh",
          color: "#888",
        }}
      >
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
      style={{ minHeight: "100vh" }}
    >
      <VoiceUI />
    </LiveKitRoom>
  );
}
