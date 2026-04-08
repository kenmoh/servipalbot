"use client";

import { 
  Badge 
} from "@/components/ui/badge";
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from "@/components/ui/table";
import { 
  Card, 
  CardContent, 
  CardHeader, 
  CardTitle,
  CardDescription
} from "@/components/ui/card";
import { MoreHorizontal, Search, Filter, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";

type Lead = {
  id: string;
  name: string;
  category?: string;
  email?: string | null;
  phone?: string | null;
  location?: string | null;
  source?: string;
  status?: string;
};

interface LeadsTableProps {
  leads: Lead[];
}

import { 
  Badge 
} from "@/components/ui/badge";
import { 
  Table, 
  TableBody, 
  TableCell, 
  TableHead, 
  TableHeader, 
  TableRow 
} from "@/components/ui/table";
import { 
  Card, 
  CardContent, 
  CardHeader, 
  CardTitle,
  CardDescription
} from "@/components/ui/card";
import { MoreHorizontal, Search, Filter, ExternalLink, Globe } from "lucide-react";
import { Button } from "@/components/ui/button";

type Lead = {
  id: string;
  name: string;
  category?: string;
  email?: string | null;
  phone?: string | null;
  location?: string | null;
  source?: string;
  status?: string;
  website?: string | null;
};

interface LeadsTableProps {
  leads: Lead[];
}

export function LeadsTable({ leads }: LeadsTableProps) {
  return (
    <Card className="border-border bg-card overflow-hidden">
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle className="text-xl font-bold text-foreground">Recent Leads</CardTitle>
          <CardDescription className="text-muted-foreground text-xs">A list of the latest potential customers discovered.</CardDescription>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="h-8 gap-1 text-[10px] border-border bg-background hover:bg-secondary">
            <Search className="h-3 w-3" />
            Search
          </Button>
          <Button variant="outline" size="sm" className="h-8 gap-1 text-[10px] border-border bg-background hover:bg-secondary">
            <Filter className="h-3 w-3" />
            Filter
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div className="overflow-x-auto">
          <Table>
            <TableHeader className="bg-secondary/30 border-y border-border">
              <TableRow className="hover:bg-transparent">
                <TableHead className="font-bold text-foreground text-[10px] uppercase tracking-wider py-3">Name</TableHead>
                <TableHead className="font-bold text-foreground text-[10px] uppercase tracking-wider py-3">Category</TableHead>
                <TableHead className="font-bold text-foreground text-[10px] uppercase tracking-wider py-3">Website</TableHead>
                <TableHead className="font-bold text-foreground text-[10px] uppercase tracking-wider py-3">Contact</TableHead>
                <TableHead className="font-bold text-foreground text-[10px] uppercase tracking-wider py-3">Status</TableHead>
                <TableHead className="text-right font-bold text-foreground text-[10px] uppercase tracking-wider py-3">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {leads.length > 0 ? (
                leads.map((lead) => (
                  <TableRow key={lead.id} className="hover:bg-secondary/20 transition-colors border-b border-border/50 last:border-0">
                    <TableCell className="font-semibold text-foreground py-4 text-sm">{lead.name}</TableCell>
                    <TableCell className="text-muted-foreground text-xs">{lead.category}</TableCell>
                    <TableCell>
                      {lead.website ? (
                        <a 
                          href={lead.website.startsWith('http') ? lead.website : `https://${lead.website}`} 
                          target="_blank" 
                          rel="noopener noreferrer"
                          className="flex items-center gap-1.5 text-primary hover:underline text-xs group"
                        >
                          <Globe className="h-3 w-3 opacity-70 group-hover:opacity-100" />
                          Visit Site
                          <ExternalLink className="h-2 w-2 opacity-0 group-hover:opacity-100 transition-opacity" />
                        </a>
                      ) : (
                        <span className="text-muted-foreground/30 text-[10px]">N/A</span>
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground text-xs">
                      {lead.email ? (
                        <div className="flex flex-col gap-0.5">
                          <span className="flex items-center gap-1 text-foreground/80 font-medium">
                            {lead.email}
                          </span>
                          <span className="text-[10px] opacity-60">{lead.phone || lead.location}</span>
                        </div>
                      ) : (
                        <span className="text-muted-foreground/30">—</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge 
                        variant="secondary" 
                        className={`rounded-full px-2 py-0.5 text-[9px] font-bold uppercase tracking-tight ${
                          lead.status === 'contacted' ? 'bg-emerald-400/10 text-emerald-400 border-emerald-400/20' :
                          lead.status === 'replied' ? 'bg-blue-400/10 text-blue-400 border-blue-400/20' :
                          'bg-secondary text-muted-foreground border-border'
                        }`}
                      >
                        {lead.status || 'New'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="icon" className="h-7 w-7 text-muted-foreground hover:text-foreground hover:bg-secondary">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              ) : (
                <TableRow>
                  <TableCell colSpan={6} className="h-32 text-center text-muted-foreground italic text-sm">
                    No leads found. Start a scrape to gather more.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}
