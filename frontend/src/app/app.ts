import { ChangeDetectionStrategy, Component, OnInit, effect, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from './core/auth/auth.service';
import { ProfileService } from './core/profile/profile.service';

@Component({
  imports: [RouterLink, RouterLinkActive, RouterOutlet],
  selector: 'app-root',
  styleUrl: './app.css',
  templateUrl: './app.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class App implements OnInit {
  protected readonly auth = inject(AuthService);
  protected readonly profile = inject(ProfileService);

  constructor() {
    effect(() => {
      const user = this.auth.currentUser();
      if (user === null) {
        this.profile.resetCosmetics();
        return;
      }
      this.profile.getCosmetics().subscribe({ error: () => undefined });
    });
  }

  ngOnInit(): void {
    this.auth.refresh().subscribe();
  }
}
