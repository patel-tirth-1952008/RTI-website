"use client";
import React from "react";
import { User, Mail, Phone, MapPin, Shield, Calendar } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useAuthStore } from "@/lib/store";
import { formatDate } from "@/lib/utils";

export default function ProfilePage() {
  const { user } = useAuthStore();

  if (!user) {
    return <div className="text-center py-20 text-slate-500">Please log in to view profile.</div>;
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-10">
      <Card gradient glow className="p-8 space-y-6">
        <div className="flex items-center gap-4 border-b border-slate-700/50 pb-6">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-2xl font-bold text-white shadow-lg">
            {user.full_name?.charAt(0) || "U"}
          </div>
          <div>
            <h1 className="text-2xl font-bold font-display text-white">{user.full_name}</h1>
            <p className="text-slate-400 text-sm">{user.email}</p>
            <div className="flex gap-2 mt-2">
              <Badge variant="info">Verified Citizen</Badge>
              {user.is_bpl && <Badge variant="success">BPL Fee Exempt</Badge>}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="bg-slate-900/60 p-4 rounded-xl">
            <p className="text-slate-500 text-xs mb-1 flex items-center gap-1.5">
              <Phone className="w-3.5 h-3.5" /> Phone Number
            </p>
            <p className="text-white font-medium text-sm">{user.phone || "Not set"}</p>
          </div>

          <div className="bg-slate-900/60 p-4 rounded-xl">
            <p className="text-slate-500 text-xs mb-1 flex items-center gap-1.5">
              <MapPin className="w-3.5 h-3.5" /> Jurisdiction / Location
            </p>
            <p className="text-white font-medium text-sm">
              {user.city ? `${user.city}, ${user.state}` : "Gujarat"}
            </p>
          </div>

          <div className="bg-slate-900/60 p-4 rounded-xl">
            <p className="text-slate-500 text-xs mb-1 flex items-center gap-1.5">
              <Calendar className="w-3.5 h-3.5" /> Member Since
            </p>
            <p className="text-white font-medium text-sm">{formatDate(user.created_at)}</p>
          </div>

          <div className="bg-slate-900/60 p-4 rounded-xl">
            <p className="text-slate-500 text-xs mb-1 flex items-center gap-1.5">
              <Shield className="w-3.5 h-3.5" /> Legal Data Privacy
            </p>
            <p className="text-green-400 font-medium text-sm">AES-128 Encrypted at Rest</p>
          </div>
        </div>
      </Card>
    </div>
  );
}