"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Room } from "livekit-client";

export default function RoomPage() {
  const { roomId } = useParams();
  const [htmlPreview, setHtmlPreview] = useState<string>("");
  const [status, setStatus] = useState("Connecting to your Wellness Companion...");

  useEffect(() => {
    const connectToRoom = async () => {
      try {
        const url = process.env.NEXT_PUBLIC_LIVEKIT_URL!;
        const tokenResp = await fetch(`/api/connection-details?room=${roomId}`);
        const { token } = await tokenResp.json();

        const room = new Room({
          adaptiveStream: true,
          dynacast: true,
        });

        room.on("dataReceived", (payload, participant, kind, topic) => {
          if (topic === "html-preview") {
            const html = new TextDecoder().decode(payload);
            setHtmlPreview(html);
          }
        });

        await room.connect(url, token);
        await room.localParticipant.setMicrophoneEnabled(true);
        setStatus("Connected. You can start speaking anytime.");

      } catch (err) {
        setStatus("Failed to connect.");
        console.error(err);
      }
    };

    connectToRoom();
  }, [roomId]);

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      padding: "40px",
      background: "#F5FFF8",
      minHeight: "100vh",
      color: "#2E5339",
      fontFamily: "sans-serif"
    }}>

      <h1 style={{
        color: "#1B7340",
        fontSize: "32px",
        fontWeight: "bold",
        marginBottom: "10px"
      }}>
        Daily Wellness Companion
      </h1>

      <p style={{ marginBottom: "20px" }}>{status}</p>

      <div style={{
        background: "white",
        borderRadius: "16px",
        padding: "20px",
        width: "320px",
        minHeight: "320px",
        boxShadow: "0 4px 10px rgba(0,0,0,0.15)"
      }}>
        {htmlPreview ? (
          <div dangerouslySetInnerHTML={{ __html: htmlPreview }} />
        ) : (
          <p style={{ textAlign: "center", marginTop: "100px", color: "#777" }}>
            Your daily check-in summary will appear here 🌿  
          </p>
        )}
      </div>
    </div>
  );
}
