import { Injectable } from '@angular/core';
import { PvPCredential } from './pvp.models';

@Injectable({ providedIn: 'root' })
export class PvPCredentialStore {
  private readonly prefix = 'kiba:pvp:';

  save(inviteCode: string, credential: PvPCredential): void {
    sessionStorage.setItem(this.key(inviteCode), JSON.stringify(credential));
  }

  get(inviteCode: string): PvPCredential | null {
    const raw = sessionStorage.getItem(this.key(inviteCode));
    if (raw === null) return null;
    try {
      const value = JSON.parse(raw) as Partial<PvPCredential>;
      if (
        typeof value.participant_id === 'string' &&
        (value.seat === 'one' ||
          value.seat === 'two' ||
          value.seat === 'three' ||
          value.seat === 'four') &&
        typeof value.reconnect_token === 'string'
      ) {
        return value as PvPCredential;
      }
    } catch {
      // Invalid ephemeral state is equivalent to no reconnect credential.
    }
    this.clear(inviteCode);
    return null;
  }

  clear(inviteCode: string): void {
    sessionStorage.removeItem(this.key(inviteCode));
  }

  private key(inviteCode: string): string {
    return `${this.prefix}${inviteCode}`;
  }
}
