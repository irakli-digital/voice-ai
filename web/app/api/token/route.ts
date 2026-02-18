import { AccessToken, AgentDispatchClient, RoomServiceClient } from "livekit-server-sdk";
import { NextRequest, NextResponse } from "next/server";

export async function POST(req: NextRequest) {
  const { room, username } = await req.json();

  const apiKey = process.env.LIVEKIT_API_KEY;
  const apiSecret = process.env.LIVEKIT_API_SECRET;
  const livekitUrl = process.env.LIVEKIT_URL;

  if (!apiKey || !apiSecret || !livekitUrl) {
    return NextResponse.json(
      { error: "LiveKit credentials not configured" },
      { status: 500 }
    );
  }

  const roomName = room || `voice-ai-${Date.now()}`;
  const participantName = username || "user";
  const httpUrl = livekitUrl.replace("wss://", "https://");

  // Create room
  const roomService = new RoomServiceClient(httpUrl, apiKey, apiSecret);
  try {
    await roomService.createRoom({ name: roomName });
    console.log(`Room created: ${roomName}`);
  } catch (e) {
    console.log("Room create:", e instanceof Error ? e.message : e);
  }

  // Explicitly dispatch agent (empty agentName = any available agent)
  try {
    const dispatch = new AgentDispatchClient(httpUrl, apiKey, apiSecret);
    await dispatch.createDispatch(roomName, "");
    console.log(`Agent dispatched to: ${roomName}`);
  } catch (e) {
    console.error("Dispatch error:", e instanceof Error ? e.message : e);
  }

  // Generate participant token
  const at = new AccessToken(apiKey, apiSecret, {
    identity: participantName,
    name: participantName,
  });

  at.addGrant({
    room: roomName,
    roomJoin: true,
    canPublish: true,
    canSubscribe: true,
  });

  const token = await at.toJwt();

  return NextResponse.json({
    token,
    url: livekitUrl,
    room: roomName,
  });
}
