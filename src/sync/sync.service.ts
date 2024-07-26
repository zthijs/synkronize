import { Injectable, Logger } from '@nestjs/common';
import { Interval } from '@nestjs/schedule';
import { ColorService } from '../color/color.service';
import { ApiTags } from '@nestjs/swagger';
import { StorageService } from 'src/storage/storage.service';
import { SpotifyService } from '@/providers/spotify/spotify.service';
import { DirigeraService } from '@/consumers/dirigera/dirigera.service';
import { ConsumerEnum } from '@/common/enums/consumers.enum';

@Injectable()
@ApiTags('sync')
export class SyncService {
  private readonly logger = new Logger(SyncService.name);

  constructor(
    private readonly spotifyService: SpotifyService,
    private readonly colorService: ColorService,
    private readonly storageService: StorageService,
    private readonly dirigeraService: DirigeraService,
  ) {}

  @Interval(1500)
  async sync() {
    try {
      const activeAccounts =
        await this.spotifyService.getActiveSpotifyAccounts();

      const colorsToUpdate = await Promise.all(
        activeAccounts.map(async ({ account, status }) => {
          const current = this.storageService.get(account.id);

          if (current !== status.id) {
            this.storageService.set(account.id, status.id);
            const colors = await this.colorService.getColors(status.image);
            return { account, status, color: colors };
          }
        }),
      );

      colorsToUpdate.filter(Boolean).forEach(({ account, color }) => {
        account.consumers
          .filter((v) => v.type === ConsumerEnum.Dirigera)
          .forEach((consumer) => {
            this.dirigeraService.setLightHSL(
              consumer.identifier,
              color[consumer.pallete].hsl,
            );
          });
      });
    } catch (error) {
      this.logger.error('Error during sync:', error);
    }
  }
}
