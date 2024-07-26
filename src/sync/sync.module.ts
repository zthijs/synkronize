import { Module } from '@nestjs/common';
import { ScheduleModule } from '@nestjs/schedule';
import { SyncService } from './sync.service';
import { ColorModule } from '../color/color.module';
import { StorageModule } from '../storage/storage.module';
import { SpotifyModule } from '@/providers/spotify/spotify.module';
import { DirigeraModule } from '@/consumers/dirigera/dirigera.module';

@Module({
  imports: [
    SpotifyModule,
    ColorModule,
    ScheduleModule.forRoot(),
    StorageModule,
    DirigeraModule,
  ],
  providers: [SyncService],
})
export class SyncModule {}
