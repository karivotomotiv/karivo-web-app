import { useState } from "react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { TrendingUp, TrendingDown } from "lucide-react";
import Gelirler from "@/pages/Gelirler";
import Giderler from "@/pages/Giderler";

export default function GelirGider() {
  const [tab, setTab] = useState("gelirler");

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-3xl font-extrabold tracking-tight text-slate-900">Gelir / Giderler</h2>
        <p className="text-sm text-slate-600 mt-1">Gelir ve gider kayıtlarını aynı yerden, iki ayrı sekmede yönetin.</p>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="grid grid-cols-2 w-full max-w-md">
          <TabsTrigger value="gelirler" data-testid="finance-tab-gelirler">
            <TrendingUp className="w-4 h-4 mr-2 text-emerald-600" /> Gelirler
          </TabsTrigger>
          <TabsTrigger value="giderler" data-testid="finance-tab-giderler">
            <TrendingDown className="w-4 h-4 mr-2 text-rose-600" /> Giderler
          </TabsTrigger>
        </TabsList>
        <TabsContent value="gelirler" className="mt-6">
          <Gelirler />
        </TabsContent>
        <TabsContent value="giderler" className="mt-6">
          <Giderler />
        </TabsContent>
      </Tabs>
    </div>
  );
}
